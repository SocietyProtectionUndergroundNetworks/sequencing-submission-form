from helpers.dbm import session_scope
from models.db_model import AppConfigurationTable
import logging

logger = logging.getLogger("my_app_logger")


class AppConfiguration:
    def __init__(self, _id, label, description, value):
        self.id = _id
        self.label = label
        self.description = description
        self.value = value

    @classmethod
    def get_all(cls):
        with session_scope() as session:
            session.expire_all()  # ensures fresh fetch from DB
            rows = session.query(AppConfigurationTable).all()
            return [cls(r.id, r.label, r.description, r.value) for r in rows]

    @classmethod
    def get_value(cls, label):
        """Return the value of a configuration entry by its label, or None if not found."""
        with session_scope() as session:
            row = (
                session.query(AppConfigurationTable)
                .filter_by(label=label)
                .first()
            )
            return row.value if row else None

    @classmethod
    def update_config(cls, label, value, description=None):
        """
        Update or create a configuration entry.
        - label = unique identifier for setting
        - value = value to store
        - description = optional description for new entries
        """
        with session_scope() as session:
            # Attempt to find existing config
            config = (
                session.query(AppConfigurationTable)
                .filter_by(label=label)
                .first()
            )

            if config:
                # Update existing
                config.value = value
                session.commit()
                session.refresh(config)
                logger.info(f"Updated configuration: {label} -> {value}")
            else:
                # Create new configuration record
                config = AppConfigurationTable(
                    label=label,
                    value=value,
                    description=description,
                )
                session.add(config)
                session.commit()
                session.refresh(config)
                logger.info(f"Created configuration entry: {label} -> {value}")

            return cls(
                config.id, config.label, config.description, config.value
            )
