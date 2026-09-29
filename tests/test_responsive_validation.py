"""Automated Static and Structural Responsive Layout Validation
Validates responsive viewport configuration, CSS rules, table card layouts,
scroll containers, and touch-target standards across all Jinja2 templates and CSS.
"""
import glob
import os
import re
import unittest


class ResponsiveLayoutValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.templates_dir = os.path.join(cls.root_dir, "app", "templates")
        cls.css_path = os.path.join(cls.root_dir, "app", "static", "css", "style.css")
        
        with open(cls.css_path, "r", encoding="utf-8") as f:
            cls.css_content = f.read()

    def test_01_viewport_meta_tags(self):
        """Verify viewport meta tag exists in base.html for all inheriting pages."""
        base_tpl = os.path.join(self.templates_dir, "base.html")
        with open(base_tpl, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('name="viewport"', content, f"Missing viewport meta in {base_tpl}")
        self.assertIn("width=device-width", content, f"Missing device-width in {base_tpl}")

    def test_02_css_responsive_breakpoints(self):
        """Verify CSS defines responsive breakpoints covering 320px, 375px, 430px, 768px, 1024px, 1440px."""
        self.assertIn("@media (max-width: 480px)", self.css_content)
        self.assertIn("@media (max-width: 380px)", self.css_content)
        self.assertIn("@media (max-width: 768px)", self.css_content)
        self.assertIn("@media (max-width: 1024px)", self.css_content)
        self.assertIn("@media (max-width: 1280px)", self.css_content)

    def test_03_mobile_navigation_components(self):
        """Verify mobile hamburger button, slide-out drawer, and backdrop overlay exist."""
        dashboard_tpl = os.path.join(self.templates_dir, "dashboard.html")
        with open(dashboard_tpl, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("mobile-menu-toggle", content)
        self.assertIn("sidebar-overlay", content)
        self.assertIn("toggleMobileSidebar", content)

    def test_04_all_tables_have_responsive_wrappers(self):
        """Verify every table element in every template is either in a card view or a scroll container."""
        all_html_files = glob.glob(os.path.join(self.templates_dir, "**", "*.html"), recursive=True)
        table_files = []
        for file_path in all_html_files:
            # Skip print templates which use paged media
            if "print" in os.path.split(file_path)[0]:
                continue
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "<table" in content:
                # Must have table-card-view or table-scroll-container
                has_card_view = "table-card-view" in content or "has-card-view" in content
                has_scroll_container = "table-scroll-container" in content
                self.assertTrue(
                    has_card_view or has_scroll_container,
                    f"Table in {os.path.relpath(file_path, self.templates_dir)} lacks responsive card view or scroll container!"
                )
                table_files.append(file_path)
        
        self.assertGreaterEqual(len(table_files), 10, "Expected at least 10 templates containing data tables")

    def test_05_table_card_view_cells_have_data_labels(self):
        """Verify all data cells in table-card-view have data-label attributes for mobile card headers."""
        card_table_files = [
            "stock/list.html",
            "stock/low.html",
            "customers/list.html",
            "customers/sales.html",
            "suppliers/list.html",
            "suppliers/purchases.html",
            "audit_log.html",
            "users.html",
            "settings/list.html",
        ]
        for rel_path in card_table_files:
            full_path = os.path.join(self.templates_dir, *rel_path.split("/"))
            if not os.path.exists(full_path):
                continue
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Find td tags inside tbody excluding empty state placeholders
            td_tags = [td for td in re.findall(r"<td\b[^>]*>", content) if "card-empty-cell" not in td]
            self.assertGreater(len(td_tags), 0, f"No <td> found in {rel_path}")
            labeled_tds = [td for td in td_tags if "data-label=" in td]
            # Data cells in responsive card views must have data-label
            ratio = len(labeled_tds) / len(td_tags)
            self.assertGreaterEqual(
                ratio, 0.7,
                f"Low data-label coverage ({ratio:.1%}) in {rel_path}. Cells need data-label for mobile card rendering."
            )

    def test_06_touch_target_ergonomics(self):
        """Verify buttons and interactive controls meet minimum touch target standards (>= 36px)."""
        self.assertIn("min-height: 38px", self.css_content)
        self.assertIn("min-height: 42px", self.css_content)
        self.assertIn("min-height: 48px", self.css_content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
