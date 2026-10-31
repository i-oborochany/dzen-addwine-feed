import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.etree import ElementTree as ET

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import progress
import publisher
import feed_io


class PlanTests(unittest.TestCase):
    def test_skip_preserves_actual_selected_index(self):
        plan = [{'number': i + 1, 'title': title} for i, title in enumerate(['blocked', 'blocked', 'allowed'])]
        index, row = progress.select_content_plan(plan, 0, lambda title: (title == 'blocked', 'filtered'))
        self.assertEqual((index, row['title']), (2, 'allowed'))
        state = {'cycle_position': 5, 'content_plan_index': index}
        progress.advance_cycle(state, 'content_plan')
        self.assertEqual(state['content_plan_index'], 3)
        self.assertEqual(state['cycle_position'], 1)

    def test_wraparound_finds_allowed_row(self):
        plan = [{'title': 'allowed'}, {'title': 'blocked'}]
        self.assertEqual(progress.select_content_plan(plan, 1, lambda title: (title == 'blocked', 'filtered'))[0], 0)

    def test_invalid_cursor_starts_at_beginning(self):
        self.assertEqual(progress.select_content_plan([{'title': 'allowed'}], 90, lambda title: (False, ''))[0], 0)

    def test_empty_or_entirely_blocked_plan_fails(self):
        for plan in [[], [{'title': 'blocked'}]]:
            with self.subTest(plan=plan):
                with self.assertRaises(RuntimeError):
                    progress.select_content_plan(plan, 0, lambda title: (True, 'filtered'))


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.article = {'title': 'Test article', 'lead': 'Test lead', 'html': '<p>Test body</p>'}
        self.images = ['images/test/cover-1.jpg']
        self.config = {'channel': {'pages_base_url': 'https://feed.addwine.ru'}}
        self.renderer = Mock()
        self.reader = patch.object(feed_io, 'read_feed', return_value={'channel': {'title': 'Journal'}, 'items': []}).start()
        self.writer = patch.object(feed_io, 'write_feed').start()
        self.modules = patch.dict(sys.modules, {'html_renderer': self.renderer})
        self.modules.start()
        self.addCleanup(patch.stopall)

    def test_render_error_does_not_save_feed(self):
        self.renderer.write_post.side_effect = RuntimeError('render failed')
        with self.assertRaises(RuntimeError):
            publisher.add_to_feed(self.article, self.images, '', self.config)
        self.writer.assert_not_called()

    def test_feed_is_written_only_after_all_rendering_succeeds(self):
        events = []
        self.renderer.rebuild_index.side_effect = lambda: events.append('rendered')
        self.writer.side_effect = lambda *args: events.append('feed')
        publisher.add_to_feed(self.article, self.images, '', self.config)
        self.assertEqual(events, ['rendered', 'feed'])

    def test_index_failure_does_not_save_feed(self):
        self.renderer.rebuild_index.side_effect = RuntimeError('index failed')
        with self.assertRaises(RuntimeError):
            publisher.add_to_feed(self.article, self.images, '', self.config)
        self.writer.assert_not_called()


class FeedDelayTests(unittest.TestCase):
    def test_24_hour_boundary_keeps_full_store_and_releases_only_mature_item(self):
        now = datetime(2026, 11, 1, 16, 0, tzinfo=timezone.utc)
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return now
        def item(name, age):
            return {'title': name, 'link': 'https://feed.addwine.ru/posts/' + name + '/',
                    'guid': name, 'pub_date': format_datetime(now - age), 'description': name,
                    'content_html': '<p>Article</p>', 'enclosure_url': '', 'enclosure_type': 'image/jpeg'}
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with patch.object(feed_io, 'FEED_PATH', folder / 'feed.xml'), patch.object(feed_io, 'FEED_FULL_PATH', folder / 'full.json'), patch.object(feed_io, 'datetime', Clock):
                feed_io.write_feed({'title': 'Journal', 'link': 'https://feed.addwine.ru/', 'description': 'Wine', 'language': 'ru'},
                                   [item('new', timedelta(hours=23, minutes=59)), item('mature', timedelta(hours=24))])
                links = [x.findtext('link') for x in ET.parse(folder / 'feed.xml').findall('./channel/item')]
                self.assertEqual(links, ['https://feed.addwine.ru/posts/mature/'])
                self.assertEqual(len(json.loads((folder / 'full.json').read_text())['items']), 2)


@unittest.skipUnless(importlib.util.find_spec('feedparser'), 'Full pipeline dependencies are tested in GitHub Actions')
class MainProgressTests(unittest.TestCase):
    def exercise(self, fail=False):
        import main
        state = {'cycle_position': 5, 'content_plan_index': 0, 'history': []}
        plan = [{'number': i + 1, 'title': title, 'promote_category': 'wine', 'promote_link': 'https://addwine.ru/', 'seo_query': 'wine'}
                for i, title in enumerate(['blocked', 'blocked', 'allowed'])]
        article = {'title_chosen': 'Test article', 'lead': 'Lead', 'html': '<p>Body</p>', 'image_prompts': []}
        with patch.dict('os.environ', {'FORCE_PUBLISH': '1'}), \
             patch.object(main.progress_mod, 'load_progress', return_value=state), \
             patch.object(main.progress_mod, 'load_content_plan', return_value=plan), \
             patch.object(main.stop_list, 'should_skip_topic', side_effect=lambda title: (title == 'blocked', 'filtered')), \
             patch.object(main.seo_planner, 'discover_keywords', return_value=[]), \
             patch.object(main.writer, 'write_content_plan_article', return_value=article), \
             patch.object(main.addwine_linker, 'fetch_links', return_value=[]), \
             patch.object(main.publisher, 'save_images', return_value=['images/test/cover-1.jpg']), \
             patch.object(main.publisher, 'add_to_feed', side_effect=RuntimeError('render failed') if fail else None), \
             patch.object(main.publisher, 'mark_published'), \
             patch.object(main.progress_mod, 'save_progress') as save:
            if fail:
                with self.assertRaises(RuntimeError):
                    main.main()
                save.assert_not_called()
                self.assertEqual(state['content_plan_index'], 0)
                self.assertEqual(state['history'], [])
            else:
                self.assertEqual(main.main(), 0)
                self.assertEqual(state['content_plan_index'], 3)
                self.assertEqual(state['cycle_position'], 1)
                save.assert_called_once()

    def test_saved_cursor_follows_selected_row(self):
        self.exercise()

    def test_failed_publication_preserves_cursor(self):
        self.exercise(fail=True)


class DigestTests(unittest.TestCase):
    def test_one_article_skips_digest_before_inference_or_publication(self):
        import main_digest
        with patch.object(main_digest.progress_mod, 'load_progress', return_value={}), \
             patch.object(main_digest.weekly_digest, 'load_posts_for_week', return_value=[{'title': 'One article'}]), \
             patch.object(main_digest.weekly_digest, 'build_digest') as generate, \
             patch.object(main_digest.publisher, 'add_to_feed') as publish:
            self.assertEqual(main_digest.main(), 0)
            generate.assert_not_called()
            publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
