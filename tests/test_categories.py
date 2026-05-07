from tests.base import BaseTestCase


class CategoryTests(BaseTestCase):

    def test_create_category(self):
        resp = self.client.post('/api/categories/', {
            'name': '自定义分类', 'category_type': 'expense',
            'icon': '📌', 'color': '#ff4d4f',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], '自定义分类')

    def _get_results(self, resp):
        return resp.data.get('results', resp.data)

    def test_list_categories_root_only(self):
        parent = self.create_category(name='娱乐', category_type='expense')
        self.create_category(name='电影', category_type='expense', parent=parent)
        self.create_category(name='游戏', category_type='expense', parent=parent)

        resp = self.client.get('/api/categories/', {'category_type': 'expense'})
        self.assertEqual(resp.status_code, 200)
        data = self._get_results(resp)
        names = [c['name'] for c in data]
        self.assertIn('娱乐', names)
        self.assertNotIn('电影', names)

    def test_category_with_children(self):
        parent = self.create_category(name='餐饮', category_type='expense')
        self.create_category(name='早餐', category_type='expense', parent=parent)

        resp = self.client.get('/api/categories/', {'category_type': 'expense'})
        data = self._get_results(resp)
        parent_item = next(c for c in data if c['name'] == '餐饮')
        self.assertEqual(len(parent_item['children']), 1)
        self.assertEqual(parent_item['children'][0]['name'], '早餐')

    def test_filter_by_type(self):
        self.create_category(name='支出分类', category_type='expense')
        self.create_category(name='收入分类', category_type='income')

        resp = self.client.get('/api/categories/', {'category_type': 'income'})
        self.assertEqual(resp.status_code, 200)
        data = self._get_results(resp)
        self.assertTrue(all(c['category_type'] == 'income' for c in data))

    def test_update_category(self):
        cat = self.create_category(name='旧名称')
        resp = self.client.patch(f'/api/categories/{cat.id}/', {'name': '新名称'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], '新名称')

    def test_delete_category(self):
        cat = self.create_category(name='待删除')
        resp = self.client.delete(f'/api/categories/{cat.id}/')
        self.assertEqual(resp.status_code, 204)

    def test_data_isolation(self):
        self.create_category(name='用户1分类')
        self.create_category(name='用户2分类', user=self.user2)

        resp = self.client.get('/api/categories/')
        data = self._get_results(resp)
        names = [c['name'] for c in data]
        self.assertIn('用户1分类', names)
        self.assertNotIn('用户2分类', names)
