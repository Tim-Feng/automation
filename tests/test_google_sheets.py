import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock logger
sys.modules['logger'] = MagicMock()

# 加入專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.google_sheets import get_next_id

class TestGoogleSheets(unittest.TestCase):
    def setUp(self):
        """每個測試前的設置"""
        self.sheet = MagicMock()
    
    def test_get_next_id_empty_sheet(self):
        """測試空白表格的情況"""
        self.sheet.col_values.return_value = ['標題1', '標題2']  # 只有標題列
        self.assertEqual(get_next_id(self.sheet), 1)
        
    def test_get_next_id_continuous_ids(self):
        """測試連續 ID 的情況"""
        self.sheet.col_values.return_value = ['標題1', '標題2', '5701', '5702', '5703']
        self.assertEqual(get_next_id(self.sheet), 5704)
        
    def test_get_next_id_with_single_gap(self):
        """測試有一個缺漏的情況"""
        self.sheet.col_values.return_value = ['標題1', '標題2', '5701', '5702', '5704']
        self.assertEqual(get_next_id(self.sheet), 5703)
        
    def test_get_next_id_with_multiple_gaps(self):
        """測試有多個缺漏的情況"""
        self.sheet.col_values.return_value = ['標題1', '標題2', '5702', '5707', '5708']
        self.assertEqual(get_next_id(self.sheet), 5703)
        
    def test_get_next_id_with_all_gaps_filled(self):
        """測試所有缺漏都填完後的情況"""
        self.sheet.col_values.return_value = ['標題1', '標題2', 
            '5702', '5703', '5704', '5705', '5706', '5707', '5708']
        self.assertEqual(get_next_id(self.sheet), 5709)
        
    def test_get_next_id_with_non_numeric_values(self):
        """測試包含非數字值的情況"""
        self.sheet.col_values.return_value = ['標題1', '標題2', '5701', 'error', '5703']
        self.assertEqual(get_next_id(self.sheet), 5702)
        
    def test_get_next_id_with_duplicate_ids(self):
        """測試有重複 ID 的情況"""
        self.sheet.col_values.return_value = ['標題1', '標題2', '5701', '5702', '5702']
        self.assertEqual(get_next_id(self.sheet), 5703)

if __name__ == '__main__':
    unittest.main()
