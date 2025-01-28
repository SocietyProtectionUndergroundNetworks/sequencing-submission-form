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
    SequencingAnalysisTable,
    SequencingAnalysisTypesTable,
    SequencingSamplesTable,
    SequencingUploadsTable,
    OTU,
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

        # Use the `with` statement to automatically handle session closing
        with get_session(db_engine) as session:
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

            # Retrieve or create each of the lookup
            # entries, passing the session
            domain_id = (
                TaxonomyManager.get_or_create(
                    Domain, domain_name, session=session
                )
                if domain_name
                else None
            )
            phylum_id = (
                TaxonomyManager.get_or_create(
                    Phylum, phylum_name, domain_id=domain_id, session=session
                )
                if phylum_name
                else None
            )
            class_id = (
                TaxonomyManager.get_or_create(
                    Class, class_name, phylum_id=phylum_id, session=session
                )
                if class_name
                else None
            )
            order_id = (
                TaxonomyManager.get_or_create(
                    Order, order_name, class_id=class_id, session=session
                )
                if order_name
                else None
            )
            family_id = (
                TaxonomyManager.get_or_create(
                    Family, family_name, order_id=order_id, session=session
                )
                if family_name
                else None
            )
            genus_id = (
                TaxonomyManager.get_or_create(
                    Genus, genus_name, family_id=family_id, session=session
                )
                if genus_name
                else None
            )
            species_id = (
                TaxonomyManager.get_or_create(
                    Species, species_name, genus_id=genus_id, session=session
                )
                if species_name
                else None
            )

            # Build the query
            filters = []
            filters.append(
                Taxonomy.domain_id == domain_id
                if domain_id is not None
                else Taxonomy.domain_id.is_(None)
            )
            filters.append(
                Taxonomy.phylum_id == phylum_id
                if phylum_id is not None
                else Taxonomy.phylum_id.is_(None)
            )
            filters.append(
                Taxonomy.class_id == class_id
                if class_id is not None
                else Taxonomy.class_id.is_(None)
            )
            filters.append(
                Taxonomy.order_id == order_id
                if order_id is not None
                else Taxonomy.order_id.is_(None)
            )
            filters.append(
                Taxonomy.family_id == family_id
                if family_id is not None
                else Taxonomy.family_id.is_(None)
            )
            filters.append(
                Taxonomy.genus_id == genus_id
                if genus_id is not None
                else Taxonomy.genus_id.is_(None)
            )
            filters.append(
                Taxonomy.species_id == species_id
                if species_id is not None
                else Taxonomy.species_id.is_(None)
            )

            # Build and execute the query
            query = session.query(Taxonomy).filter(*filters)

            # Execute the query
            existing_taxonomy = query.first()

            if existing_taxonomy:
                # If it exists, return the ID
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
                return taxonomy_id

    @staticmethod
    def get_or_create(model, name, session=None, **kwargs):
        """
        Get the ID of an existing entry in the lookup
        table or create a new one if it doesn't exist.
        """
        # Skip creation if the name is "?" or None
        if name in ["?", None]:
            return None

        # If a session is provided, use it; otherwise, create a new session
        if session is None:
            return None
        else:

            # Try to get the record
            record = session.query(model).filter(model.name == name).first()

            if not record:
                # If it doesn't exist, create it
                record = model(name=name, **kwargs)
                session.add(record)
                session.commit()

            record_id = record.id

            return record_id

    @classmethod
    def search(
        cls,
        domain=None,
        phylum=None,
        class_=None,
        order=None,
        family=None,
        genus=None,
        species=None,
        project=None,
    ):
        """
        Search for taxonomies based on the given parameters.
        """
        db_engine = connect_db()
        session = get_session(db_engine)

        # Join SequencingSamplesTable with OTU, Taxonomy
        # and SequencingUploadsTable
        query = (
            session.query(
                OTU.sample_id,
                SequencingSamplesTable.SampleID,
                SequencingSamplesTable.Longitude,
                SequencingSamplesTable.Latitude,
                SequencingUploadsTable.id.label("upload_id"),
                SequencingUploadsTable.project_id,
                Taxonomy,
                OTU.abundance,
                SequencingAnalysisTypesTable.name.label("analysis_type"),
            )
            .join(OTU, OTU.sample_id == SequencingSamplesTable.id)
            .join(Taxonomy, OTU.taxonomy_id == Taxonomy.id)
            .join(
                SequencingUploadsTable,
                SequencingSamplesTable.sequencingUploadId
                == SequencingUploadsTable.id,
            )
            .join(
                SequencingAnalysisTable,
                OTU.sequencing_analysis_id == SequencingAnalysisTable.id,
            )
            .join(
                SequencingAnalysisTypesTable,
                SequencingAnalysisTable.sequencingAnalysisTypeId
                == SequencingAnalysisTypesTable.id,
            )
        )

        # Dynamically add filters based on provided arguments
        if domain:
            query = query.filter(Taxonomy.domain.has(name=domain))
        if phylum:
            query = query.filter(Taxonomy.phylum.has(name=phylum))
        if class_:
            query = query.filter(Taxonomy.class_.has(name=class_))
        if order:
            query = query.filter(Taxonomy.order.has(name=order))
        if family:
            query = query.filter(Taxonomy.family.has(name=family))
        if genus:
            query = query.filter(Taxonomy.genus.has(name=genus))
        if species:
            query = query.filter(Taxonomy.species.has(name=species))
        if project:
            query = query.filter(SequencingUploadsTable.project_id == project)
        results = query.all()

        # Format the results
        formatted_results = [
            {
                "sample_id": row.sample_id,
                "SampleID": row.SampleID,
                "upload_id": row.upload_id,
                "project_id": row.project_id,
                "Latitude": row.Latitude,
                "Longitude": row.Longitude,
                "abundance": row.abundance,
                "analysis_type": row.analysis_type,
                "domain": (
                    row.Taxonomy.domain.name if row.Taxonomy.domain else None
                ),
                "phylum": (
                    row.Taxonomy.phylum.name if row.Taxonomy.phylum else None
                ),
                "class": (
                    row.Taxonomy.class_.name if row.Taxonomy.class_ else None
                ),
                "order": (
                    row.Taxonomy.order.name if row.Taxonomy.order else None
                ),
                "family": (
                    row.Taxonomy.family.name if row.Taxonomy.family else None
                ),
                "genus": (
                    row.Taxonomy.genus.name if row.Taxonomy.genus else None
                ),
                "species": (
                    row.Taxonomy.species.name if row.Taxonomy.species else None
                ),
            }
            for row in results
        ]

        session.close()
        return formatted_results

    @classmethod
    def get_otus(cls, sample_id, region, analysis_type_id):
        db_engine = connect_db()
        session = get_session(db_engine)
        query = (
            session.query(
                Taxonomy,
                OTU.abundance,
                OTU.sample_id,
                SequencingAnalysisTypesTable.name.label("analysis_type"),
            )
            .join(
                Taxonomy, OTU.taxonomy_id == Taxonomy.id
            )  # Join with Taxonomy
            .join(
                SequencingAnalysisTable,
                OTU.sequencing_analysis_id == SequencingAnalysisTable.id,
            )  # Join with SequencingAnalysisTable
            .join(
                SequencingAnalysisTypesTable,
                SequencingAnalysisTable.sequencingAnalysisTypeId
                == SequencingAnalysisTypesTable.id,
            )  # Join with SequencingAnalysisTypesTable
        )

        # Apply filter for sample_id (always required)
        query = query.filter(OTU.sample_id == sample_id)

        # Conditionally add region filter
        if region in ["ITS1", "ITS2", "SSU"]:
            query = query.filter(SequencingAnalysisTypesTable.region == region)

        # Check if the analysis_type_id is a valid integer
        if analysis_type_id and analysis_type_id.isdigit():
            analysis_type_id = int(analysis_type_id)
            # Conditionally add analysis_type_id filter if it's numeric
            query = query.filter(
                SequencingAnalysisTypesTable.id == analysis_type_id
            )

        results = query.all()

        # Format the results
        formatted_results = [
            {
                "abundance": int(row.abundance),
                "analysis_type": row.analysis_type,
                "domain": (
                    row.Taxonomy.domain.name if row.Taxonomy.domain else None
                ),
                "phylum": (
                    row.Taxonomy.phylum.name if row.Taxonomy.phylum else None
                ),
                "class": (
                    row.Taxonomy.class_.name if row.Taxonomy.class_ else None
                ),
                "order": (
                    row.Taxonomy.order.name if row.Taxonomy.order else None
                ),
                "family": (
                    row.Taxonomy.family.name if row.Taxonomy.family else None
                ),
                "genus": (
                    row.Taxonomy.genus.name if row.Taxonomy.genus else None
                ),
                "species": (
                    row.Taxonomy.species.name if row.Taxonomy.species else None
                ),
            }
            for row in results
        ]

        session.close()
        return formatted_results
