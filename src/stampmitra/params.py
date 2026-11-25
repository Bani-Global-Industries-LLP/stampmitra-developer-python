"""Request-body types for the e-Stamp order routes (plain ``TypedDict`` s; keys are the wire names).

Every method also accepts an ordinary ``dict``. A ``firstParty`` / ``secondParty`` is either a bare name string or an
:class:`EstampParty` object; use the object whenever the state wants an address or a father's / husband's name.
"""

from __future__ import annotations

from typing import List, Literal, TypedDict, Union

__all__ = ["EstampOrderRequest", "EstampParty", "EstampPropertyArea", "EstampStampLine"]


class _EstampPartyRequired(TypedDict):
    name: str


class EstampParty(_EstampPartyRequired, total=False):
    """One party to the instrument (unknown keys are rejected by the API with UNKNOWN_FIELD)."""

    address: str
    phone: str
    fatherHusbandName: str
    gender: Literal["MALE", "FEMALE", "OTHER"]


class _EstampPropertyAreaRequired(TypedDict):
    unit: Literal["Square Feet", "Square Yard", "Square Meters", "Not Applicable"]


class EstampPropertyArea(_EstampPropertyAreaRequired, total=False):
    #: Required (and > 0) unless ``unit`` is ``"Not Applicable"``.
    value: float


class _EstampStampLineRequired(TypedDict):
    state: str
    articleCode: str
    denomination: float
    firstParty: Union[str, EstampParty]


class EstampStampLine(_EstampStampLineRequired, total=False):
    """One stamp line. ``quantity`` is 1 to 1000 (default 1)."""

    clientReference: str
    category: Literal["e_stamp", "traditional_stamp"]
    stampDutyPayer: str
    payerPhone: str
    payerGender: Literal["MALE", "FEMALE", "OTHER"]
    secondParty: Union[str, EstampParty]
    purpose: str
    district: str
    sro: str
    cessAmount: float
    propertyArea: EstampPropertyArea
    #: https link to the payer's PAN card. An order can be placed without it, but a PAN card is mandatory to complete the stamp.
    panCardImage: str
    costCentre: str
    businessUnit: str
    linkedDocRef: str
    quantity: int


class _EstampOrderRequestRequired(TypedDict):
    #: 1 to 5000 lines, all in one state.
    stamps: List[EstampStampLine]


class EstampOrderRequest(_EstampOrderRequestRequired, total=False):
    reference: str
