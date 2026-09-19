import unittest
from elemzes.hungarian_scan import seller_description, product_brand

class ScopedEvidenceTests(unittest.TestCase):
    def test_navigation_is_not_product_evidence(self):
        html='<nav>Herendi eozin hibátlan</nav><h2>Eladó leírása a termékről</h2><p>Tungsram, nem mért.</p><h2>Szállítási feltételek</h2><p>Herendi</p>'
        self.assertEqual(seller_description(html),'Tungsram, nem mért.')
        self.assertEqual(product_brand('2db ECC83 Tungsram'),'Tungsram')
    def test_missing_description_stays_unknown(self):
        self.assertEqual(seller_description('<nav>Hibátlan porcelán</nav>'),'')
        self.assertEqual(product_brand('Elektroncső'),'Ismeretlen')

if __name__=='__main__':
    unittest.main()
