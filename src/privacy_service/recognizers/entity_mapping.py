"""Entity type mapping between ai4privacy and Presidio.

Supports:
- ai4privacy library: State-of-the-art PII detection with specific entity classification
- CamemBERT-NER: Standard NER tags for French (PER, ORG, LOC, MISC) - legacy support
- Other French NER models - legacy support

This module maps entity types from ai4privacy to Presidio's standard entity types.
"""

# Mapping for French NER models (CamemBERT-NER standard tags)
FRENCH_NER_TO_PRESIDIO_MAPPING = {
    "PER": "PERSON",
    "PERS": "PERSON",
    "PERSON": "PERSON",
    "ORG": "ORGANIZATION",
    "LOC": "LOCATION",
    "MISC": "MISC",
}

# Mapping from ai4privacy entity types to Presidio entity types
# Based on ai4privacy library's entity classification
AI4PRIVACY_TO_PRESIDIO_MAPPING = {
    # Generic label (when classify_pii=False)
    "PRIVATE": "PII",
    # Person identifiers
    "GIVENNAME": "PERSON",
    "FIRSTNAME": "PERSON",
    "LASTNAME": "PERSON",
    "SURNAME": "PERSON",
    "MIDDLENAME": "PERSON",
    "NAME": "PERSON",
    "USERNAME": "PERSON",
    "TITLE": "PERSON",
    "PREFIX": "PERSON",
    "SUFFIX": "PERSON",
    # Contact information
    "EMAIL": "EMAIL_ADDRESS",
    "PHONENUMBER": "PHONE_NUMBER",
    "PHONE": "PHONE_NUMBER",
    "TELEPHONENUM": "PHONE_NUMBER",
    "FAX": "PHONE_NUMBER",
    # Location identifiers
    "STREET": "LOCATION",
    "CITY": "LOCATION",
    "STATE": "LOCATION",
    "COUNTY": "LOCATION",
    "ZIPCODE": "LOCATION",
    "COUNTRY": "LOCATION",
    "ADDRESS": "LOCATION",
    "BUILDINGNUMBER": "LOCATION",
    "BUILDINGNUM": "LOCATION",
    "SECONDARYADDRESS": "LOCATION",
    # Organization identifiers
    "COMPANYNAME": "ORGANIZATION",
    "ORGANIZATION": "ORGANIZATION",
    # Financial identifiers
    "CREDITCARDNUMBER": "CREDIT_CARD",
    "CREDITCARD": "CREDIT_CARD",
    "ACCOUNTNUMBER": "ACCOUNT_NUMBER",
    "ACCOUNTNUM": "ACCOUNT_NUMBER",
    "IBAN": "IBAN_CODE",
    "BIC": "IBAN_CODE",
    "CURRENCYCODE": "CURRENCY",
    "CURRENCYNAME": "CURRENCY",
    "AMOUNT": "AMOUNT",
    "BITCOINADDRESS": "CRYPTO",
    "ETHEREUMADDRESS": "CRYPTO",
    # Government IDs
    "SSN": "US_SSN",
    "SOCIALNUM": "US_SSN",
    "SOCIALSECURITYNUMBER": "US_SSN",
    "TAXID": "TAX_ID",
    "TAX": "TAX_ID",
    "DRIVERSLICENSE": "US_DRIVER_LICENSE",
    "PASSPORT": "US_PASSPORT",
    "IDCARD": "ID_CARD",
    # Date/Time
    "DATE": "DATE_TIME",
    "TIME": "DATE_TIME",
    "DOB": "DATE_TIME",
    "DATEOFBIRTH": "DATE_TIME",
    # Technical identifiers
    "IP": "IP_ADDRESS",
    "IPADDRESS": "IP_ADDRESS",
    "IPADDR": "IP_ADDRESS",
    "URL": "URL",
    "MAC": "MAC_ADDRESS",
    "MACADDRESS": "MAC_ADDRESS",
    # Other identifiers
    "AGE": "AGE",
    "SEX": "GENDER",
    "GENDER": "GENDER",
    "PASSWORD": "PASSWORD",
    "PASS": "PASSWORD",
    "PIN": "PIN",
    "VEHICLEVRM": "LICENSE_PLATE",
    "MASKEDNUMBER": "MASKED_ID",
}

# Reverse mapping (Presidio to ai4privacy types)
PRESIDIO_TO_AI4PRIVACY_MAPPING: dict[str, list[str]] = {}
for ai4p_type, presidio_type in AI4PRIVACY_TO_PRESIDIO_MAPPING.items():
    if presidio_type not in PRESIDIO_TO_AI4PRIVACY_MAPPING:
        PRESIDIO_TO_AI4PRIVACY_MAPPING[presidio_type] = []
    PRESIDIO_TO_AI4PRIVACY_MAPPING[presidio_type].append(ai4p_type)


def map_ai4privacy_to_presidio(ai4privacy_entity: str) -> str:
    """Map NER entity type to Presidio entity type.

    Supports multiple NER models (ai4privacy, CamemBERT-NER, etc.)

    Args:
        ai4privacy_entity: Entity type from NER model

    Returns:
        Corresponding Presidio entity type, or original if no mapping exists
    """
    # Normalize to uppercase
    entity = ai4privacy_entity.upper().replace(" ", "")

    # Try French NER mapping first (for CamemBERT-NER models)
    if entity in FRENCH_NER_TO_PRESIDIO_MAPPING:
        return FRENCH_NER_TO_PRESIDIO_MAPPING[entity]

    # Try ai4privacy mapping
    if entity in AI4PRIVACY_TO_PRESIDIO_MAPPING:
        return AI4PRIVACY_TO_PRESIDIO_MAPPING[entity]

    # If no mapping exists, use the original type as-is
    # This preserves model-specific entity types
    return entity


def get_all_ai4privacy_entities() -> list:
    """Get list of all ai4privacy entity types.

    Returns:
        List of ai4privacy entity types
    """
    return list(AI4PRIVACY_TO_PRESIDIO_MAPPING.keys())


def get_all_presidio_entities() -> list:
    """Get list of all mapped Presidio entity types.

    Returns:
        List of Presidio entity types from all supported models
    """
    all_entities = set(AI4PRIVACY_TO_PRESIDIO_MAPPING.values())
    all_entities.update(FRENCH_NER_TO_PRESIDIO_MAPPING.values())
    return list(all_entities)
