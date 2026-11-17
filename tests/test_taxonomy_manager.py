from models.db_model import Taxonomy
from models.taxonomy import TaxonomyManager


def test_get_or_create_returns_none_for_nan_without_hitting_the_db():
    """
    A taxonomy CSV cell LotuS3 couldn't resolve down to a given rank is
    read by pandas as float('nan'). Passing that straight to
    get_or_create used to reach a real DB query with nan bound as a
    parameter, which MySQLdb rejects with "nan can not be used with
    MySQL" (seen for ITS2_eukaryome analyses, where Eukaryome-sourced
    taxonomy strings leave unresolved ranks blank rather than "?").
    """
    assert TaxonomyManager.get_or_create(Taxonomy, float("nan")) is None


def test_create_handles_nan_genus_like_missing_genus(db_session):
    """
    create() should treat a NaN genus_name (unresolved rank) the same
    way it already treats an explicit "?" placeholder: Genus/Species end
    up unset on the Taxonomy row instead of the call crashing.
    """
    taxonomy_id = TaxonomyManager.create(
        domain_name="Fungi",
        phylum_name="Basidiomycota",
        class_name="Agaricomycetes",
        order_name="Russulales",
        family_name="Russulaceae",
        genus_name=float("nan"),
        species_name=float("nan"),
        session=db_session,
    )

    assert taxonomy_id is not None

    taxonomy = db_session.query(Taxonomy).filter_by(id=taxonomy_id).first()
    assert taxonomy.family_id is not None
    assert taxonomy.genus_id is None
    assert taxonomy.species_id is None
