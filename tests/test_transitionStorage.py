from unittest import TestCase
from shine import TransitionStorage


class TestTransitionStorage(TestCase):
    def test_add_items(self):
        t = TransitionStorage()
        t.add_items([((1, 2), 6, -1, (1, 3)), ((1, 3), 5, -1, (1, 3))])
        self.assertEqual(len(t), 2)

    def test_get_random_items(self):
        t = TransitionStorage()
        t.add_items([((1, 2), 6, -1, (1, 3)), ((1, 3), 5, -1, (1, 3))])
        sample = t.get_random_items(1)
        self.assertEqual(type(sample), list)
        self.assertEqual(type(sample[0]), tuple)
        self.assertEqual(len(sample), 1)
        self.assertEqual(len(t), 2)


if __name__ == '__main__':
    unittest.main()

