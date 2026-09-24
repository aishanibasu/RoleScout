"""Canonical US state names shared by current and previously collected listings."""

STATE_NAMES = dict(
    pair.split(":", 1)
    for pair in (
        "AL:Alabama|AK:Alaska|AZ:Arizona|AR:Arkansas|CA:California|CO:Colorado|"
        "CT:Connecticut|DE:Delaware|DC:District of Columbia|FL:Florida|GA:Georgia|"
        "HI:Hawaii|ID:Idaho|IL:Illinois|IN:Indiana|IA:Iowa|KS:Kansas|KY:Kentucky|"
        "LA:Louisiana|ME:Maine|MD:Maryland|MA:Massachusetts|MI:Michigan|MN:Minnesota|"
        "MS:Mississippi|MO:Missouri|MT:Montana|NE:Nebraska|NV:Nevada|NH:New Hampshire|"
        "NJ:New Jersey|NM:New Mexico|NY:New York|NC:North Carolina|ND:North Dakota|"
        "OH:Ohio|OK:Oklahoma|OR:Oregon|PA:Pennsylvania|RI:Rhode Island|SC:South Carolina|"
        "SD:South Dakota|TN:Tennessee|TX:Texas|UT:Utah|VT:Vermont|VA:Virginia|"
        "WA:Washington|WV:West Virginia|WI:Wisconsin|WY:Wyoming|PR:Puerto Rico|"
        "VI:U.S. Virgin Islands|GU:Guam|AS:American Samoa|MP:Northern Mariana Islands"
    ).split("|")
)


_STATE_BY_NAME = {name.casefold(): name for name in STATE_NAMES.values()}


def country_name(value):
    value = (value or "").strip()
    return (
        "United States"
        if value.casefold() in {"us", "usa", "u.s.", "united states", "united states of america"}
        else value
    )


def state_name(value, country):
    value = (value or "").strip()
    if country_name(country) != "United States":
        return value
    return STATE_NAMES.get(value.upper(), _STATE_BY_NAME.get(value.casefold(), value))


def normalize_locations(item):
    locations = [
        dict(
            loc,
            country=country_name(loc.get("country")),
            region=state_name(loc.get("region"), loc.get("country")),
        )
        for loc in item.get("locations", [])
    ]
    if not locations:
        return item
    return {
        **item,
        "locations": locations,
        **{
            key: " | ".join(dict.fromkeys(loc.get(key, "") for loc in locations if loc.get(key)))
            for key in ("city", "region", "country")
        },
    }
