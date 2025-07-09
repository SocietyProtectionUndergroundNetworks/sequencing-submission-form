from flask import Blueprint

upload_form_bp = Blueprint("upload_form_bp", __name__)

# Import your view modules *after* the blueprint is defined
# These imports are here to ensure the routes within them are registered
from . import fastq  # noqa: E402, F401
from . import lotus2  # noqa: E402, F401
from . import rscripts  # noqa: E402, F401
from . import pdf_and_share  # noqa: E402, F401
from . import mapping_files  # noqa: E402, F401
from . import form_general  # noqa: E402, F401
from . import samples  # noqa: E402, F401
from . import sequencer_ids  # noqa: E402, F401
from . import files_upload  # noqa: E402, F401
