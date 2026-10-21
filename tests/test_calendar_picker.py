import tkinter as tk
import unittest
from app.calendar_picker import DateCalendar


class CalendarTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.value = tk.StringVar(value='31/12/2026 14:30')

    def test_year_navigation_and_click_preserves_time(self):
        popup = DateCalendar(self.root, self.value)
        popup.move(1)
        self.assertEqual((popup.year, popup.month), (2027, 1))
        button = next(w for w in popup.days.winfo_children() if w.winfo_class() == 'TButton' and w.cget('text') == '5')
        button.invoke()
        self.assertEqual(self.value.get(), '05/01/2027 14:30')
        self.assertEqual(self.root.grab_current(), self.root)

    def test_leap_day_and_cancel(self):
        self.value.set('01/02/2024')
        popup = DateCalendar(self.root, self.value)
        button = next(w for w in popup.days.winfo_children() if w.winfo_class() == 'TButton' and w.cget('text') == '29')
        button.invoke()
        self.assertEqual(self.value.get(), '29/02/2024')
        popup = DateCalendar(self.root, self.value)
        popup.move(-1)
        popup.close()
        self.assertEqual(self.value.get(), '29/02/2024')
