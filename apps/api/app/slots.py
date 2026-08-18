from __future__ import annotations

import re
from dataclasses import dataclass

from .interpret import apply_discriminator, detect_state, interpret, intent_of
from .schemas import Intent, SlotQuestion


@dataclass
class SlotSpec:
    key: str
    prompt_en: str
    prompt_hi: str
    required: bool = True
    extract_patterns: tuple[str, ...] = ()


RTI_SLOTS = [
    SlotSpec("applicant_name", "What is your full name (as it should appear on the RTI)?", "आरटीआई पर आपका पूरा नाम क्या है?"),
    SlotSpec("applicant_address", "What is your complete postal address?", "आपका पूरा डाक पता क्या है?"),
    SlotSpec("applicant_contact", "Phone or email where the PIO can reach you?", "फोन या ईमेल जिस पर PIO आपसे संपर्क कर सके?"),
    SlotSpec("state", "Which State / UT is this about?", "यह किस राज्य / केंद्र शासित प्रदेश के बारे में है?"),
    SlotSpec(
        "public_authority",
        "Which department or office holds the record, if you know?",
        "किस विभाग / कार्यालय के पास रिकॉर्ड है?",
        required=False,
    ),
    SlotSpec(
        "information_sought",
        "In one paragraph, what exact information or copies do you want?",
        "आप कौन-सी सटीक जानकारी या प्रतियाँ चाहते हैं?",
        required=False,
    ),
    SlotSpec("period", "What period should the information cover (dates / months)?", "जानकारी किस अवधि की चाहिए?", required=False),
]

CONSUMER_SLOTS = [
    SlotSpec("complainant_name", "Your full name?", "आपका पूरा नाम?"),
    SlotSpec("complainant_address", "Your address (this often decides which District Commission)?", "आपका पता (जिला आयोग यहीं से तय होता है)?"),
    SlotSpec("opposite_party", "Name of the shop / company / seller?", "दुकान / कंपनी / विक्रेता का नाम?"),
    SlotSpec("opposite_party_address", "Seller address, if you have it.", "विक्रेता का पता, यदि पता हो।", required=False),
    SlotSpec("goods_service", "What did you buy or which service did you hire?", "आपने क्या खरीदा या कौन सी सेवा ली?"),
    SlotSpec("amount", "How much did you pay (₹)?", "आपने कितने रुपये दिए?"),
    SlotSpec("purchase_date", "Date of purchase / booking?", "खरीद / बुकिंग की तारीख?"),
    SlotSpec("defect", "What is wrong, and how did the seller refuse to help?", "क्या खराबी है, और विक्रेता ने मदद से कैसे मना किया?"),
    SlotSpec("relief", "What do you want — refund, replacement, repair, compensation?", "आप क्या चाहते हैं — वापसी, बदली, मरम्मत, मुआवजा?"),
]

TENANT_SLOTS = [
    SlotSpec("tenant_name", "Your name?", "आपका नाम?"),
    SlotSpec("tenant_contact", "Phone or email?", "फोन या ईमेल?"),
    SlotSpec("landlord_name", "Landlord's name?", "मकान मालिक का नाम?"),
    SlotSpec("premises", "Full address of the rented house?", "किराये के मकान का पूरा पता?"),
    SlotSpec("state", "State / UT of the premises?", "मकान किस राज्य में है?"),
    SlotSpec("issue", "What exactly happened (electricity cut, 2-day eviction notice, etc.)?", "ठीक क्या हुआ?"),
    SlotSpec("facts_date", "When did this happen?", "यह कब हुआ?"),
]


SLOTS: dict[Intent, list[SlotSpec]] = {
    "rti": RTI_SLOTS,
    "consumer": CONSUMER_SLOTS,
    "tenant": TENANT_SLOTS,
    "nhrc": [],
    "unsupported": [],
}

AMOUNT = re.compile(r"(?:₹|rs\.?|inr|rupees?)\s*([0-9][0-9,]*)", re.I)
BARE_AMOUNT = re.compile(r"\b([0-9]{4,7})\b")


def extract_from_text(intent: Intent, text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    interp = interpret(text, {})
    if interp.benefit:
        found.setdefault("benefit", interp.benefit)
    st = detect_state(text)
    if st:
        found.setdefault("state", st)
    if intent == "consumer":
        m = AMOUNT.search(text) or BARE_AMOUNT.search(text)
        if m:
            found["amount"] = m.group(1).replace(",", "")
        if re.search(r"phone|smartphone|mobile", text, re.I):
            found.setdefault("goods_service", "smartphone")
        if re.search(r"refund", text, re.I):
            found.setdefault("relief", "Refund of the purchase amount with compensation for harassment")
        if re.search(r"lucknow", text, re.I):
            found.setdefault("complainant_address", "Lucknow, Uttar Pradesh")
        if re.search(r"last month", text, re.I):
            found.setdefault("purchase_date", "last month (exact date to be filled by complainant)")
        if re.search(r"refused|no returns", text, re.I):
            found.setdefault(
                "defect",
                "Device is defective; seller refused refund citing a no-returns policy.",
            )
        if re.search(r"shop", text, re.I):
            found.setdefault("opposite_party", "The retail shop that sold the goods (name to be completed)")
    if intent == "nhrc":
        found.setdefault("facts", text.strip()[:800])
        if re.search(r"slap", text, re.I):
            found.setdefault("issue", "Alleged slap / use of force by a police officer.")
    if intent == "tenant":
        if re.search(r"electric", text, re.I):
            found.setdefault("issue", "Landlord withheld electricity / essential supply and demanded vacation of the premises.")
        if re.search(r"two days|2 days|vacate", text, re.I):
            found["issue"] = found.get("issue", "") + " Informal notice to vacate within two days."
    return {k: v.strip() for k, v in found.items() if v.strip()}


def next_question(intent: Intent, slots: dict[str, str], text: str = "") -> SlotQuestion | None:
    interp = interpret(text, slots)
    from .interpret import discriminating_question

    dq = discriminating_question(interp, slots)
    if dq:
        return dq
    for spec in SLOTS.get(intent, []):
        if spec.required and not slots.get(spec.key):
            return SlotQuestion(key=spec.key, prompt_en=spec.prompt_en, prompt_hi=spec.prompt_hi, required=True)
    return None


def apply_answer(intent: Intent, slots: dict[str, str], current_key: str | None, text: str) -> dict[str, str]:
    updated = apply_discriminator(slots, current_key, text)
    auto = extract_from_text(intent_of(interpret(" ".join(updated.values()) + " " + text, updated)), text)
    for k, v in auto.items():
        updated.setdefault(k, v)
    if current_key and current_key not in ("pending_kind", "scheme_level") and text.strip():
        updated[current_key] = text.strip()
    return updated
