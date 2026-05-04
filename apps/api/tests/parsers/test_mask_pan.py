from app.parsers.samsung_card import mask_pan


def test_mask_pan_full():
    masked, last4 = mask_pan("1234-5678-9012-3456")
    assert masked == "****-****-****-3456"
    assert last4 == "3456"


def test_mask_pan_no_dashes():
    masked, last4 = mask_pan("1234567890123456")
    assert masked == "****-****-****-3456"
    assert last4 == "3456"


def test_mask_pan_short():
    masked, last4 = mask_pan("12")
    assert masked == "****-****-****-****"
    assert last4 == ""


def test_mask_pan_empty():
    masked, last4 = mask_pan("")
    assert masked == "****-****-****-****"
    assert last4 == ""
