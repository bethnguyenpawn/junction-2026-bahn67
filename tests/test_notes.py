"""notes.py on real notes from cached weeks; expected values are the revealed truth."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DAY, HOUR
from notes import due, one_typo, open_interval, read


def at(day: int, hour: int, minute: int = 0) -> int:
    return day * DAY + hour * HOUR + minute


def facts(text: str, arrived: int, language: str = "fi"):
    return read({"text": text, "language": language}, arrived)


class ReadyTime(unittest.TestCase):
    def test_tomorrow(self):
        self.assertEqual(
            facts("Ready for pickup from tomorrow 10:30. Key box code 6440.", at(0, 14), "en").ready, at(1, 10, 30)
        )

    def test_weekday_is_two_to_six_days_ahead(self):
        self.assertEqual(facts("Huolto kesken, valmis torstaina klo 13.00", at(0, 14)).ready, at(3, 13))
        self.assertEqual(facts("Huolto kesken, valmis ke klo 13.", at(0, 11)).ready, at(2, 13))

    def test_hour_in_words(self):
        self.assertEqual(
            facts("haettava ennen klo 20.00. tännään puoli neljältä valmis", at(2, 11)).ready, at(2, 15, 30)
        )
        self.assertEqual(facts("noudettavissa aikaisintaan huomenna kahdeltatoista.", at(0, 10)).ready, at(1, 12))

    def test_payment_and_swedish(self):
        self.assertEqual(facts("Utlämning efter betalning, från i morgon klockan 11", at(3, 17), "sv").ready, at(4, 11))
        self.assertEqual(facts("Buyer pays first, picukp from 1:30pm.", at(2, 9), "en").ready, at(2, 13, 30))

    def test_correction_and_denial(self):
        self.assertEqual(
            facts("Noudettavissa aikaisintaan huomenna klo 12.30, eikun klo 11.30", at(3, 11)).ready, at(4, 11, 30)
        )
        self.assertEqual(facts("huolto kesken, valmis huomenna klo 9. korjaus: klo 10.", at(0, 15)).ready, at(1, 10))
        self.assertEqual(facts("auto valmis vasta klo 11.30 (ei klo 12.30)", at(3, 8)).ready, at(3, 11, 30))

    def test_typos(self):
        self.assertEqual(
            facts("Ostaja maksaa ensin, auton saa humoenna klo 11.30 alkaen", at(3, 14)).ready, at(4, 11, 30)
        )

    def test_opening_hours_are_not_a_ready_time(self):
        self.assertIsNone(facts("Noudettavissa arkisin 10-15.30. Tilausnumero 544941", at(4, 12)).ready)


class Deadline(unittest.TestCase):
    def test_tomorrow_and_weekday(self):
        self.assertEqual(facts("Toimitus perille viim. huomenna klo 12", at(0, 13)).deadline, at(1, 12))
        self.assertEqual(facts("Must be at destination by Mon 19:00", at(1, 9), "en").deadline, at(7, 19))

    def test_correction_keeps_the_time(self):
        note = "toimitus perille viim. sunnuntaina klo 16.30, eikun maanantaina!"
        self.assertEqual(facts(note, at(4, 13)).deadline, at(7, 16, 30))
        self.assertEqual(
            facts("Terve. Perillä sunnuntaina kello 19 mennessä. Korjaus: maanantaina.", at(4, 15)).deadline, at(7, 19)
        )

    def test_hour_words_and_compact_clock(self):
        self.assertEqual(facts("perillä huomenna viiteen mennessä.", at(3, 10)).deadline, at(4, 17))
        self.assertEqual(facts("Moikka. Perillä huomenna kello 1900 mennessä.", at(3, 14)).deadline, at(4, 19))

    def test_mixed_note(self):
        note = "hei vaan. auto valmis vasta huomenna klo 7. oltava perillä viimeistään to klo 14."
        f = facts(note, at(1, 19))
        self.assertEqual((f.ready, f.deadline), (at(2, 7), at(3, 14)))

    def test_closing_time_cuts_the_deadline_day(self):
        f = facts("Destination closes at 16:30.", at(3, 16), "en")
        self.assertEqual((f.deadline, f.delivery_close), (None, at(0, 16, 30)))
        self.assertEqual(due(f, at(4, 20)), at(4, 16, 30))
        self.assertEqual(facts("vastaanotto onnistuu arkisn 9:stä 15:een.", at(0, 13)).delivery_close, 15 * HOUR)


class PickupHours(unittest.TestCase):
    def test_hours_in_notes(self):
        self.assertEqual(facts("Nouto ennen klo 14.30", 0).pickup_hours, (0, at(0, 14, 30)))
        self.assertEqual(facts("Klo 9-14.30 nouto onnistuu. t. myynti", 0).pickup_hours, (at(0, 9), at(0, 14, 30)))
        self.assertEqual(facts("noudettavissa ma–pe 9:stä 17:ään, kiitti.", 0).pickup_hours, (at(0, 9), at(0, 17)))
        self.assertEqual(facts("We close at 16:30. Coorrection: 15:30!", 0, "en").pickup_hours, (0, at(0, 15, 30)))
        self.assertIsNone(facts("Kohde auki arkisin 8.00 - 20.00.", 0).pickup_hours)  # the delivery site's

    def test_one_reachable_interval(self):
        window, hours = {"from": at(3, 9, 28), "to": at(4, 20)}, (0, at(0, 14, 30))
        self.assertEqual(open_interval(window, hours, at(3, 10)), {"from": at(3, 9, 28), "to": at(3, 14, 30)})
        self.assertEqual(open_interval(window, hours, at(3, 13)), {"from": at(4, 0), "to": at(4, 14, 30)})
        self.assertEqual(open_interval(window, hours, at(4, 16)), window)  # none left: the window as it was


class Driver(unittest.TestCase):
    def test_plates(self):
        for text, language in (
            ("Ei kilpiä, siirtokilvet mukaan. Soita kun olet lähellä", "fi"),
            ("skyltarna borttagna, ta med provksyltar.", "sv"),
            ("No plates, bring transfer plates.", "en"),
            ("Ei rekkareita, koeiklvet tarvitaan.", "fi"),
        ):
            self.assertTrue(facts(text, 0, language).plates, text)
        self.assertFalse(facts("Ska vara på plats senast i morgon klockan 19.", 0, "sv").plates)

    def test_manual(self):
        self.assertTrue(facts("Manuaali, ei automaatti", 0).manual)
        self.assertTrue(facts("It's a maunal", 0, "en").manual)
        self.assertFalse(facts("Automaattivaihteinen, ei manuaali", 0).manual)

    def test_one_typo(self):
        self.assertTrue(one_typo("huomeenna", "huomenna"))
        self.assertTrue(one_typo("destiantion", "destination"))  # two neighbours swapped
        self.assertFalse(one_typo("dsetinatoin", "destination"))  # two typos
        self.assertFalse(one_typo("valsmi", "valmis"))
        self.assertTrue(one_typo("perilä", "perillä"))


if __name__ == "__main__":
    unittest.main()
