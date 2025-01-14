import logging
from helpers.dbm import connect_db, get_session
from models.db_model import (
    Domain,
    Phylum,
    Class,
    Order,
    Family,
    Genus,
    Species,
    Taxonomy,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")


class TaxonomyManager:
    @classmethod
    def get(cls, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        taxonomy_db = session.query(Taxonomy).filter_by(id=id).first()
        session.close()

        if not taxonomy_db:
            return None

        # Assuming taxonomy_db is an instance of some SQLAlchemy model
        taxonomy_db_dict = taxonomy_db.__dict__

        # Remove keys starting with '_'
        filtered_dict = {
            key: value
            for key, value in taxonomy_db_dict.items()
            if not key.startswith("_")
        }

        # Return as a dictionary or an object instance
        return filtered_dict

    @classmethod
    def create(
        cls,
        domain_name,
        phylum_name,
        class_name,
        order_name,
        family_name,
        genus_name,
        species_name,
    ):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Handle "?" by setting subsequent levels to None
        if domain_name == "?":
            phylum_name = class_name = order_name = family_name = (
                genus_name
            ) = species_name = None
        elif phylum_name == "?":
            class_name = order_name = family_name = genus_name = (
                species_name
            ) = None
        elif class_name == "?":
            order_name = family_name = genus_name = species_name = None
        elif order_name == "?":
            family_name = genus_name = species_name = None
        elif family_name == "?":
            genus_name = species_name = None
        elif genus_name == "?":
            species_name = None

        # Retrieve or create each of the lookup entries
        domain_id = (
            TaxonomyManager.get_or_create(Domain, domain_name)
            if domain_name
            else None
        )
        phylum_id = (
            TaxonomyManager.get_or_create(
                Phylum, phylum_name, domain_id=domain_id
            )
            if phylum_name
            else None
        )
        class_id = (
            TaxonomyManager.get_or_create(
                Class, class_name, phylum_id=phylum_id
            )
            if class_name
            else None
        )
        order_id = (
            TaxonomyManager.get_or_create(Order, order_name, class_id=class_id)
            if order_name
            else None
        )
        family_id = (
            TaxonomyManager.get_or_create(
                Family, family_name, order_id=order_id
            )
            if family_name
            else None
        )
        genus_id = (
            TaxonomyManager.get_or_create(
                Genus, genus_name, family_id=family_id
            )
            if genus_name
            else None
        )
        species_id = (
            TaxonomyManager.get_or_create(
                Species, species_name, genus_id=genus_id
            )
            if species_name
            else None
        )

        # Now check if this exact taxonomy combination exists
        existing_taxonomy = (
            session.query(Taxonomy)
            .filter(
                Taxonomy.domain_id == domain_id if domain_id else None,
                Taxonomy.phylum_id == phylum_id if phylum_id else None,
                Taxonomy.class_id == class_id if class_id else None,
                Taxonomy.order_id == order_id if order_id else None,
                Taxonomy.family_id == family_id if family_id else None,
                Taxonomy.genus_id == genus_id if genus_id else None,
                Taxonomy.species_id == species_id if species_id else None,
            )
            .first()
        )

        if existing_taxonomy:
            # If it exists, return the ID
            session.close()
            return existing_taxonomy.id
        else:
            # If not, create a new taxonomy record
            new_taxonomy = Taxonomy(
                domain_id=domain_id,
                phylum_id=phylum_id,
                class_id=class_id,
                order_id=order_id,
                family_id=family_id,
                genus_id=genus_id,
                species_id=species_id,
            )
            session.add(new_taxonomy)
            session.commit()
            taxonomy_id = new_taxonomy.id
            session.close()
            return taxonomy_id

    @staticmethod
    def get_or_create(model, name, **kwargs):
        """
        Get the ID of an existing entry in the lookup
        table or create a new one if it doesn't exist.
        """
        # Skip creation if the name is "?" or None
        if name in ["?", None]:
            return None

        db_engine = connect_db()
        session = get_session(db_engine)

        # Try to get the record
        record = session.query(model).filter(model.name == name).first()

        if not record:
            # If it doesn't exist, create it
            record = model(name=name, **kwargs)
            session.add(record)
            session.commit()

        record_id = record.id
        session.close()
        return record_id
