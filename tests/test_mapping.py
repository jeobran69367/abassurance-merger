from src.etl.mapping import map_ab_client, map_ap_user, map_batch


def test_map_ab_client_basic():
    row = {
        "AB_CLIENT_ID": "1001",
        "AB_NOM": "Martin",
        "AB_PRENOM": "Sophie",
        "AB_DATE_NAISSANCE": "1985-04-12",
        "AB_EMAIL": "sophie.martin@mail.com",
        "AB_TELEPHONE": "0612345678",
        "AB_ADRESSE": "12 rue des Lilas",
        "AB_CODE_POSTAL": "75011",
        "AB_NUM_FISCAL": "FR123456",
        "AB_DATE_CREATION": "2015-06-01",
        "AB_STATUT_CLIENT": "ACTIF",
    }
    result = map_ab_client(row)
    assert result["source_system"] == "ABASSURANCE"
    assert result["nom"] == "Martin"
    assert result["statut_client"] == "ACTIF"
    assert str(result["date_naissance"]) == "1985-04-12"


def test_map_ap_user_splits_full_name_and_normalizes_status():
    row = {
        "AP_USER_ID": "2001",
        "AP_FULL_NAME": "Nicolas Dubois",
        "AP_BIRTH_DATE": "1988-06-15",
        "AP_MAIL_ADDRESS": "nicolas.dubois@mail.com",
        "AP_PHONE_NUMBER": "0699887766",
        "AP_STREET_ADDRESS": "10 rue de la Paix",
        "AP_ZIP_CODE": "75002",
        "AP_CREATED_AT": "2016-02-10 09:00:00",
        "AP_CUSTOMER_STATUS": "ACTIVE",
        "AP_LOYALTY_SCORE": 72,
    }
    result = map_ap_user(row)
    assert result["source_system"] == "ASSUREPLUS"
    assert result["nom"] == "Nicolas"
    assert result["prenom"] == "Dubois"
    assert result["statut_client"] == "ACTIF"
    assert result["score_fidelite"] == 72


def test_map_batch_isolates_invalid_rows_in_quarantine():
    rows = [
        {
            "AP_USER_ID": "2004",
            "AP_FULL_NAME": "Lea Girard",
            "AP_BIRTH_DATE": "1983-03-18",
            "AP_MAIL_ADDRESS": "lea.girard@mail.com",
            "AP_PHONE_NUMBER": "badphonenumber!!!",
            "AP_STREET_ADDRESS": "1 place Bellecour",
            "AP_ZIP_CODE": "69002",
            "AP_CREATED_AT": "2013-07-07 08:45:00",
            "AP_CUSTOMER_STATUS": "ACTIVE",
            "AP_LOYALTY_SCORE": 60,
        }
    ]
    mapped, quarantine = map_batch(rows, map_ap_user)
    assert len(mapped) == 0
    assert len(quarantine) == 1
    assert "Téléphone invalide" in quarantine[0]["error"]
