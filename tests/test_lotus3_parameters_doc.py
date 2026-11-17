import glob
import os

from helpers.lotus2 import get_lotus3_parameters_doc

# The full set of SequencingAnalysisTypesTable.name values this doc is
# meant to cover (confirmed against the DB at the time this test was
# written). If a new analysis type is added, add it here too -- that's
# the signal to also document it in metadataconfig/lotus3_parameters.json.
KNOWN_ANALYSIS_TYPES = {
    "ITS1",
    "ITS2",
    "ITS1_eukaryome",
    "ITS2_eukaryome",
    "SSU_dada2",
    "SSU_vsearch",
    "SSU_eukaryome",
    "FULL_ITS_UNITE",
    "FULL_ITS_Eukaryome",
    "FULL_ITS_LSU_UNITE",
    "FULL_ITS_LSU_Eukaryome",
}


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_known_analysis_type_is_documented_exactly_once():
    doc = get_lotus3_parameters_doc()

    seen = []
    for group in doc["parameter_groups"]:
        seen.extend(group["analysis_types"])

    # No typos/stale entries: everything documented is a real analysis type.
    assert set(seen) <= KNOWN_ANALYSIS_TYPES, (
        f"doc references unknown analysis type(s): "
        f"{set(seen) - KNOWN_ANALYSIS_TYPES}"
    )
    # Nothing missing: every real analysis type is documented...
    assert KNOWN_ANALYSIS_TYPES <= set(seen), (
        f"analysis type(s) missing from the doc: "
        f"{KNOWN_ANALYSIS_TYPES - set(seen)}"
    )
    # ...exactly once (not split/duplicated across groups).
    assert len(seen) == len(set(seen)), "an analysis type appears in >1 group"


def test_every_sdm_file_on_disk_is_documented_and_vice_versa():
    doc = get_lotus3_parameters_doc()
    documented = {sdm["filename"] for sdm in doc["sdm_files"]}

    on_disk = {
        os.path.basename(p)
        for p in glob.glob(
            os.path.join(_repo_root(), "lotus2_files", "sdm_*.txt")
        )
    }

    assert (
        on_disk <= documented
    ), f"sdm file(s) on disk but not documented: {on_disk - documented}"
    assert (
        documented <= on_disk
    ), f"documented sdm file(s) no longer on disk: {documented - on_disk}"


def test_every_entry_has_the_required_fields():
    doc = get_lotus3_parameters_doc()

    for group in doc["parameter_groups"]:
        for param in group["parameters"]:
            assert param.get("flag")
            assert "what_it_does" in param and param["what_it_does"]
            assert "why_we_chose_it" in param

    for sdm in doc["sdm_files"]:
        assert sdm.get("filename")
        assert sdm.get("what_it_does")
        assert "why_we_chose_it" in sdm
