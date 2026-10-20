"""Public integration coverage; access limitations stay visible alongside listings."""


def scope(source_id):
    from .collect import ADAPTERS

    adapter = ADAPTERS.get(source_id)
    if source_id == "hudsonbay":
        return "The official careers page provides careers@hudsonbaycapital.com for inquiries; no public job listing feed was found. Open the careers page for details."
    if source_id == "hft":
        return "Third-party aggregator metadata. Full requirements remain on the original employer website."
    return getattr(
        adapter,
        "SCOPE",
        "Public career listings; requirements are extracted from available descriptions.",
    )
