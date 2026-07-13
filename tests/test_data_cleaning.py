import pytest

from src.cleaning.data_cleaning import (
    DataQualityError,
    deduplicate_clients,
    normalize_annual_premium,
    normalize_status,
    parse_flexible_date,
    split_full_name,
    validate_email,
    validate_phone,
)


class TestParseFlexibleDate:
    def test_parses_iso_date(self):
        assert str(parse_flexible_date("2020-01-15")) == "2020-01-15"

    def test_parses_datetime_string(self):
        assert str(parse_flexible_date("2020-01-15 14:30:00")) == "2020-01-15"

    def test_parses_french_format(self):
        assert str(parse_flexible_date("15/01/2020")) == "2020-01-15"

    def test_returns_none_for_empty(self):
        assert parse_flexible_date(None) is None
        assert parse_flexible_date("") is None

    def test_raises_on_invalid_format(self):
        with pytest.raises(DataQualityError):
            parse_flexible_date("not-a-date")


class TestSplitFullName:
    def test_simple_name(self):
        assert split_full_name("Nicolas Dubois") == ("Nicolas", "Dubois")

    def test_compound_name(self):
        # Heuristique : dernier mot = prénom. Documenté comme limite connue.
        assert split_full_name("Anne De La Fontaine") == ("Anne De La", "Fontaine")

    def test_raises_on_empty(self):
        with pytest.raises(DataQualityError):
            split_full_name("")


class TestNormalizeStatus:
    @pytest.mark.parametrize(
        "raw,expected",
        [("ACTIVE", "ACTIF"), ("ACTIF", "ACTIF"), ("closed", "INACTIF"), ("SUSPENDED", "SUSPENDU")],
    )
    def test_known_statuses(self, raw, expected):
        assert normalize_status(raw) == expected

    def test_raises_on_unknown_status(self):
        with pytest.raises(DataQualityError):
            normalize_status("UNKNOWN_STATUS")

    def test_raises_on_missing_status(self):
        with pytest.raises(DataQualityError):
            normalize_status(None)


class TestValidateEmail:
    def test_valid_email(self):
        assert validate_email("Test@Mail.com") == "test@mail.com"

    def test_none_is_allowed(self):
        assert validate_email(None) is None

    def test_invalid_email_raises(self):
        with pytest.raises(DataQualityError):
            validate_email("not-an-email")


class TestValidatePhone:
    def test_valid_phone_is_normalized(self):
        assert validate_phone("06 12 34 56 78") == "0612345678"

    def test_invalid_phone_raises(self):
        with pytest.raises(DataQualityError):
            validate_phone("badphonenumber!!!")


class TestNormalizeAnnualPremium:
    def test_monthly_to_annual(self):
        assert normalize_annual_premium(100, is_monthly=True) == 1200

    def test_annual_stays_same(self):
        assert normalize_annual_premium(1200, is_monthly=False) == 1200

    def test_negative_raises(self):
        with pytest.raises(DataQualityError):
            normalize_annual_premium(-10, is_monthly=False)


class TestDeduplicateClients:
    def test_deduplicates_on_email_and_birthdate(self):
        clients = [
            {"email": "a@a.com", "date_naissance": "2000-01-01", "telephone": None},
            {"email": "a@a.com", "date_naissance": "2000-01-01", "telephone": "0600000000"},
            {"email": "b@b.com", "date_naissance": "1999-01-01", "telephone": None},
        ]
        deduped, duplicates = deduplicate_clients(clients)
        assert len(deduped) == 2
        assert len(duplicates) == 1
        # Le champ manquant du premier enregistrement doit être complété par le doublon.
        merged = next(c for c in deduped if c["email"] == "a@a.com")
        assert merged["telephone"] == "0600000000"
