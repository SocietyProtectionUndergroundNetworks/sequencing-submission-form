import logging
from helpers.dbm import session_scope
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
    OTU,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")


class TaxonomyManager:
    @classmethod
    def get(cls, id):
        with session_scope() as session:

            taxonomy_db = session.query(Taxonomy).filter_by(id=id).first()

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
        session,
    ):

        if domain_name and domain_name != "" and domain_name != "?":
            # Handle "?" by setting subsequent levels to None
            if phylum_name == "?":
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
            return None

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
        amf_filter=None,
        ecm_filter=None,
        analysis_type=None,
    ):
        """
        Search for taxonomies based on the given parameters.
        """
        with session_scope() as session:

            # Join SequencingSamplesTable with OTU, Taxonomy
            # and SequencingUploadsTable
            from sqlalchemy import text

            # Base SQL query
            sql_query = """
            SELECT
                o.sample_id,
                ss.SampleID,
                ss.Longitude,
                ss.Latitude,
                su.id AS upload_id,
                su.project_id,
                t.id AS taxonomy_id,
                taxonomy_domain.name AS domain_name,
                taxonomy_phylum.name AS phylum_name,
                taxonomy_class.name AS class_name,
                taxonomy_order.name AS order_name,
                taxonomy_family.name AS family_name,
                taxonomy_genus.name AS genus_name,
                taxonomy_species.name AS species_name,
                o.abundance,
                o.ecm_flag,
                sat.name AS analysis_type
            FROM sequencing_samples AS ss
                INNER JOIN otu AS o
                    ON o.sample_id = ss.id
                INNER JOIN taxonomy AS t
                    ON o.taxonomy_id = t.id
                INNER JOIN sequencing_uploads AS su
                    ON ss.sequencingUploadId = su.id
                INNER JOIN sequencing_analysis AS sa
                    ON o.sequencing_analysis_id = sa.id
                INNER JOIN sequencing_analysis_types AS sat
                    ON sa.sequencingAnalysisTypeId = sat.id
                LEFT JOIN taxonomy_domain
                    ON t.domain_id = taxonomy_domain.id
                LEFT JOIN taxonomy_phylum
                    ON t.phylum_id = taxonomy_phylum.id
                LEFT JOIN taxonomy_class
                    ON t.class_id = taxonomy_class.id
                LEFT JOIN taxonomy_order
                    ON t.order_id = taxonomy_order.id
                LEFT JOIN taxonomy_family
                    ON t.family_id = taxonomy_family.id
                LEFT JOIN taxonomy_genus
                    ON t.genus_id = taxonomy_genus.id
                LEFT JOIN taxonomy_species
                    ON t.species_id = taxonomy_species.id
            """

            # Build dynamic WHERE conditions
            filters = []
            query_params = {}

            if domain:
                filters.append("taxonomy_domain.name = :domain")
                query_params["domain"] = domain
            if phylum:
                filters.append("taxonomy_phylum = :phylum")
                query_params["phylum"] = phylum
            if class_:
                filters.append("taxonomy_class.name = :class_")
                query_params["class_"] = class_
            if order:
                filters.append("taxonomy_order.name = :order")
                query_params["order"] = order
            if family:
                filters.append("taxonomy_family.name = :family")
                query_params["family"] = family
            if genus:
                filters.append("taxonomy_genus.name = :genus")
                query_params["genus"] = genus
            if species:
                filters.append("taxonomy_species.name = :species")
                query_params["species"] = species
            if project:
                filters.append("su.project_id = :project")
                query_params["project"] = project
            if analysis_type:
                filters.append("sat.id = :analysis_type")
                query_params["analysis_type"] = analysis_type
            if ecm_filter:
                filters.append("o.ecm_flag = 1")
            if amf_filter:
                filters.append("t.class_id IN (25, 26, 27)")

            # Apply WHERE conditions if filters exist
            if filters:
                sql_query += " WHERE " + " AND ".join(filters)

            # Log the final SQL query for debugging
            # logger.info(f"Executing raw SQL: {sql_query}")

            # Execute the query
            result = session.execute(text(sql_query), query_params)

            # Fetch results
            results = result.fetchall()

            # Log the number of results
            # logger.info(f"Retrieved rows: {len(results)}")

            # Format results
            formatted_results = [
                {
                    "sample_id": row.sample_id,
                    "SampleID": row.SampleID,
                    "Longitude": row.Longitude,
                    "Latitude": row.Latitude,
                    "upload_id": row.upload_id,
                    "project_id": row.project_id,
                    "abundance": row.abundance,
                    "ecm_flag": row.ecm_flag,
                    "analysis_type": row.analysis_type,
                    "domain": row.domain_name if row.domain_name else None,
                    "phylum": row.phylum_name if row.phylum_name else None,
                    "class": row.class_name if row.class_name else None,
                    "order": row.order_name if row.order_name else None,
                    "family": row.family_name if row.family_name else None,
                    "genus": row.genus_name if row.genus_name else None,
                    "species": row.species_name if row.species_name else None,
                }
                for row in results
            ]

            return formatted_results

    @classmethod
    def get_otus(
        cls, sample_id, region, analysis_type_id, amf_filter, ecm_filter
    ):
        with session_scope() as session:
            query = (
                session.query(
                    Taxonomy,
                    OTU.abundance,
                    OTU.sample_id,
                    OTU.ecm_flag,
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
                query = query.filter(
                    SequencingAnalysisTypesTable.region == region
                )

            # Check if the analysis_type_id is a valid integer
            if analysis_type_id and analysis_type_id.isdigit():
                analysis_type_id = int(analysis_type_id)
                # Conditionally add analysis_type_id filter if it's numeric
                query = query.filter(
                    SequencingAnalysisTypesTable.id == analysis_type_id
                )
            if ecm_filter == 1:
                query = query.filter(OTU.ecm_flag == 1)
            # New filter logic for Glomeromycetes,
            # Archaeosporomycetes, and Paraglomeromycetes
            if amf_filter == 1:
                # Query the Class table to get the IDs of the specific classes
                class_ids = (
                    session.query(Class.id)
                    .filter(
                        Class.name.in_(
                            [
                                "Glomeromycetes",
                                "Archaeosporomycetes",
                                "Paraglomeromycetes",
                            ]
                        )
                    )
                    .all()
                )

                # Extract the IDs from the result
                class_ids = [class_id[0] for class_id in class_ids]

                # Apply the filter using the dynamically retrieved IDs
                query = query.filter(Taxonomy.class_id.in_(class_ids))

            results = query.all()

            # Format the results
            formatted_results = [
                {
                    "abundance": int(row.abundance),
                    "analysis_type": row.analysis_type,
                    "ecm_flag": row.ecm_flag,
                    "domain": (
                        row.Taxonomy.domain.name
                        if row.Taxonomy.domain
                        else None
                    ),
                    "phylum": (
                        row.Taxonomy.phylum.name
                        if row.Taxonomy.phylum
                        else None
                    ),
                    "class": (
                        row.Taxonomy.class_.name
                        if row.Taxonomy.class_
                        else None
                    ),
                    "order": (
                        row.Taxonomy.order.name if row.Taxonomy.order else None
                    ),
                    "family": (
                        row.Taxonomy.family.name
                        if row.Taxonomy.family
                        else None
                    ),
                    "genus": (
                        row.Taxonomy.genus.name if row.Taxonomy.genus else None
                    ),
                    "species": (
                        row.Taxonomy.species.name
                        if row.Taxonomy.species
                        else None
                    ),
                }
                for row in results
            ]

            return formatted_results
