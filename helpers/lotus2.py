import docker
import logging
import re
import shutil
import os
from datetime import datetime
from helpers.hetzner_vm import run_lotus3_on_vm

# Note: Even though for legacy reasons the module
# and all the variables and field names are called lotus2,
# we are actually using lotus3 for the report generation.

# PROCESS_DIR =
logger = logging.getLogger("my_app_logger")


def parse_lotus2_read_stats(lotus2_result_text):
    """
    Extracts read-count stats from the sdm summary block lotus2/lotus3
    prints partway through its console output, e.g.:

        Reads processed: 4,957,343; 4,957,343 (pair 1;pair 2)
        Accepted (High qual): 4,182,802; 4,440,985 (4,092; 951,604
        end-trimmed)
        Accepted (Mid qual): 174;0
        Rejected: 774,367; 516,358

    That full console output (stdout+stderr) is already saved verbatim as
    SequencingAnalysisTable.lotus2_result when a run finishes, so this
    parses the value already in hand -- no extra file reads or DB storage
    needed.

    "Reads processed" reports the same read-pair count for both mates
    (pair 1 / pair 2), but accept/reject decisions are made per-mate, so
    the pool being classified is 2x that pair count -- Accepted(High) +
    Accepted(Mid) + Rejected always sums to exactly that.

    Returns None if the text is empty or doesn't contain this block --
    e.g. a run that errored before reaching this stage, so lotus2_result
    holds an error message instead.
    """
    if not lotus2_result_text:
        return None

    def pair(label):
        match = re.search(
            rf"{label}:\s*([\d,]+)\s*;\s*([\d,]+)", lotus2_result_text
        )
        if not match:
            return None
        return (
            int(match.group(1).replace(",", "")),
            int(match.group(2).replace(",", "")),
        )

    processed = pair("Reads processed")
    high_qual = pair(r"Accepted \(High qual\)")
    mid_qual = pair(r"Accepted \(Mid qual\)")
    rejected = pair("Rejected")

    if not (processed and high_qual and mid_qual and rejected):
        return None

    starting_reads = processed[0]
    total_accepted = sum(high_qual) + sum(mid_qual)
    total_rejected = sum(rejected)
    total_classified = total_accepted + total_rejected

    return {
        "starting_reads": starting_reads,
        "accepted": total_accepted,
        "accepted_pct": (
            round(total_accepted / total_classified * 100, 1)
            if total_classified
            else None
        ),
        "rejected": total_rejected,
        "rejected_pct": (
            round(total_rejected / total_classified * 100, 1)
            if total_classified
            else None
        ),
    }


def parse_lotus2_progout_sample_blocks(text):
    """
    Parses a LotuS_progout.log file's per-sample blocks (sdm processes and
    reports on one input file pair at a time), returning accepted-read
    counts (high qual / mid qual) keyed by each sample's R1 AND R2
    filenames as lotus2 itself refers to them -- i.e. the app's own
    standardized new_name (e.g. "P_whitesand_01_ITS2_1.fastq.gz"), not the
    original filename the user uploaded:

        {"P_whitesand_01_ITS2_1.fastq.gz": {"high_qual": 344440, "mid_qual": 6},
         "P_whitesand_01_ITS2_2.fastq.gz": {"high_qual": 344440, "mid_qual": 6}}

    Both filenames map to the same values (the block covers the pair
    together), so callers can look up by whichever of the two new_name
    values they have on hand without needing to know which one is R1 vs
    R2.

    A typical block looks like:
        Input File:  /seq_processed/.../P_whitesand_01_ITS2_1.fastq.gz,P_whitesand_01_ITS2_2.fastq.gz
        Output File: /tmp/demulti.1.fna

        Reads processed: 202,800; 202,800 (pair 1;pair 2)
        58;58 reads reverse-translated, 58 read pairs swapped
        Rejected: 42,879; 18,275
        Accepted (High qual): 159,915; 184,525 (259; 15,187 end-trimmed)
        Accepted (Mid qual): 6;0
    """
    block_re = re.compile(
        r"Input File:\s*(\S+?)\s*,\s*(\S+?)\s*\n"
        r".*?Accepted \(High qual\):\s*([\d,]+)\s*;\s*([\d,]+)"
        r".*?Accepted \(Mid qual\):\s*([\d,]+)\s*;\s*([\d,]+)",
        re.DOTALL,
    )

    def num(value):
        return int(value.replace(",", ""))

    results = {}
    for match in block_re.finditer(text):
        r1_path, r2_name, h1, h2, m1, m2 = match.groups()
        stats = {
            "high_qual": num(h1) + num(h2),
            "mid_qual": num(m1) + num(m2),
        }
        results[os.path.basename(r1_path)] = stats
        results[os.path.basename(r2_name)] = stats
    return results


def update_sequencer_read_stats_from_progout(
    process_id, flask_relative_input_dir, region, analysis_type_name
):
    """
    Parses the LotuS_progout.log just produced by a finished lotus2 run and
    merges each sample's Accepted (High/Mid qual) counts onto its matching
    SequencingSequencerIDsTable row for this project+region.

    This is called once, right when an analysis finishes (see
    generate_lotus2_report below), rather than re-parsed on every page
    view: LotuS_progout.log files run 70KB-250KB+ each and a project can
    have several per region (one per analysis type), so re-reading and
    regexing all of them on every metadata_form page load would be far
    more expensive than the rare, one-off cost of parsing once here.

    A project's region is typically processed by more than one analysis
    type (e.g. ITS2 and ITS2_eukaryome), each producing its own
    LotuS_progout.log from the same underlying sdm step -- so the numbers
    are expected to agree, but aren't assumed to: every analysis type's
    result for a sample is accumulated in that row's
    progout_stats_by_analysis_type JSON column, and the flat
    progout_accepted_high_qual/progout_accepted_mid_qual columns are kept
    populated only while every analysis type seen so far agrees; as soon as
    two disagree, those flat columns are cleared (set back to None) so the
    UI knows to fall back to showing the full per-analysis-type breakdown
    from the JSON column instead of a single (potentially misleading)
    number.

    Only meaningful for real projects, not meta-projects (which combine
    already-uploaded samples from other projects rather than owning their
    own SequencingSequencerIDsTable rows) -- callers should skip this for
    is_meta runs.
    """
    progout_log_path = os.path.join(
        flask_relative_input_dir,
        "lotus2_report",
        analysis_type_name,
        "LotuSLogS",
        "LotuS_progout.log",
    )
    if not os.path.isfile(progout_log_path):
        logger.warning(
            "Cannot update per-sample read stats: %s not found",
            progout_log_path,
        )
        return

    with open(progout_log_path) as f:
        parsed = parse_lotus2_progout_sample_blocks(f.read())

    if not parsed:
        logger.warning(
            "No parseable sample blocks found in %s", progout_log_path
        )
        return

    from helpers.dbm import session_scope
    from models.db_model import (
        SequencingSequencerIDsTable,
        SequencingSamplesTable,
        SequencingFilesUploadedTable,
    )

    with session_scope() as session:
        sequencer_rows = (
            session.query(SequencingSequencerIDsTable)
            .join(
                SequencingSamplesTable,
                SequencingSamplesTable.id
                == SequencingSequencerIDsTable.sequencingSampleId,
            )
            .filter(
                SequencingSamplesTable.sequencingUploadId == process_id,
                SequencingSequencerIDsTable.Region == region,
            )
            .all()
        )
        for seq in sequencer_rows:
            file_names = [
                row[0]
                for row in session.query(SequencingFilesUploadedTable.new_name)
                .filter(SequencingFilesUploadedTable.sequencerId == seq.id)
                .all()
            ]
            stats = next(
                (parsed[name] for name in file_names if name in parsed),
                None,
            )
            if stats is None:
                continue

            existing = dict(seq.progout_stats_by_analysis_type or {})
            existing[analysis_type_name] = stats
            seq.progout_stats_by_analysis_type = existing

            unique_values = {
                (v["high_qual"], v["mid_qual"]) for v in existing.values()
            }
            if len(unique_values) == 1:
                seq.progout_accepted_high_qual = stats["high_qual"]
                seq.progout_accepted_mid_qual = stats["mid_qual"]
            else:
                seq.progout_accepted_high_qual = None
                seq.progout_accepted_mid_qual = None


def backfill_progout_read_stats_for_all_projects():
    """
    One-off maintenance sweep: for every real-project (non-meta) lotus2
    analysis that has already finished, (re-)parses its LotuS_progout.log
    and populates SequencingSequencerIDsTable's progout_accepted_high_qual
    / progout_accepted_mid_qual / progout_stats_by_analysis_type columns --
    the same columns update_sequencer_read_stats_from_progout() populates
    automatically the moment each *new* analysis finishes.

    Meant to backfill projects that were analysed before that feature
    existed. Run once from the shell (not via a web route -- sweeping
    every project's every finished analysis type reads/regexes a lot of
    on-disk log files and would very plausibly exceed a normal HTTP
    request timeout):

        docker-compose exec flask python backfill_progout_read_stats.py

    or directly against a running production container:

        docker exec -it spun-flask python3 backfill_progout_read_stats.py

    Safe to re-run -- each analysis type's contribution is simply
    recomputed and overwritten in place, same as the live per-analysis
    update does, so an interrupted run can just be started again.
    """
    from helpers.dbm import session_scope
    from models.db_model import (
        SequencingAnalysisTable,
        SequencingAnalysisTypesTable,
        SequencingUploadsTable,
    )

    with session_scope() as session:
        rows = (
            session.query(
                SequencingAnalysisTable.sequencingUploadId,
                SequencingAnalysisTypesTable.region,
                SequencingAnalysisTypesTable.name,
                SequencingUploadsTable.uploads_folder,
            )
            .join(
                SequencingAnalysisTypesTable,
                SequencingAnalysisTypesTable.id
                == SequencingAnalysisTable.sequencingAnalysisTypeId,
            )
            .join(
                SequencingUploadsTable,
                SequencingUploadsTable.id
                == SequencingAnalysisTable.sequencingUploadId,
            )
            .filter(
                # Meta-project analyses have sequencingUploadId NULL and
                # metaProjectId set instead -- they don't own their own
                # SequencingSequencerIDsTable rows, so skip them.
                SequencingAnalysisTable.sequencingUploadId.isnot(None),
                SequencingAnalysisTable.lotus2_status == "Finished",
            )
            .all()
        )

    total = len(rows)
    print(f"Found {total} finished (non-meta) lotus2 analyses to backfill.")

    succeeded = 0
    skipped = 0
    failed = 0
    for i, (
        process_id,
        region,
        analysis_type_name,
        uploads_folder,
    ) in enumerate(rows, start=1):
        flask_relative_input_dir = os.path.join(
            "seq_processed", uploads_folder
        )
        progout_log_path = os.path.join(
            flask_relative_input_dir,
            "lotus2_report",
            analysis_type_name,
            "LotuSLogS",
            "LotuS_progout.log",
        )
        label = (
            f"[{i}/{total}] process_id={process_id} region={region} "
            f"analysis_type={analysis_type_name}"
        )
        if not os.path.isfile(progout_log_path):
            print(f"{label}: SKIP -- {progout_log_path} not found")
            skipped += 1
            continue
        try:
            update_sequencer_read_stats_from_progout(
                process_id,
                flask_relative_input_dir,
                region,
                analysis_type_name,
            )
            print(f"{label}: OK")
            succeeded += 1
        except Exception as e:
            print(f"{label}: FAILED -- {e}")
            logger.exception("Backfill failed for %s", label)
            failed += 1

    print(
        f"\nDone. {succeeded} succeeded, {skipped} skipped (no log file "
        f"on disk), {failed} failed, out of {total} total."
    )


def init_generate_lotus2_report(
    process_id,
    input_dir,
    region,
    debug=False,
    analysis_type_id="0",
    parameters={},
    is_meta=False,
):
    from tasks import generate_lotus2_report_async

    from models.sequencing_analysis import SequencingAnalysis

    if analysis_type_id != 0:
        analysis_id = SequencingAnalysis.create(
            process_id, analysis_type_id, is_meta=is_meta
        )
        analysis = SequencingAnalysis.get(analysis_id)
        status = analysis.lotus2_status

        if status is None:
            try:
                result = generate_lotus2_report_async.delay(
                    process_id,
                    input_dir,
                    region,
                    debug,
                    analysis_type_id,
                    parameters,
                    is_meta=is_meta,
                )
                logger.info(
                    f"Celery generate_lotus2_report_async task "
                    f"called successfully! Task ID: {result.id}"
                )

                if analysis_id != 0:
                    SequencingAnalysis.update_field(
                        analysis_id, "lotus2_celery_task_id", result.id
                    )

            except Exception as e:
                logger.error(
                    "This is an error message from helpers/lotus2.py "
                    " while trying to generate_lotus2_report_async"
                )
                logger.error(e)
                return {
                    "error": (
                        "This is an error message from helpers/lotus2.py "
                        " while trying to generate_lotus2_report_async"
                    ),
                    "e": (e),
                }
            return {"msg": "Process initiated"}
        else:
            return {
                "msg": "Cannot initiate the process as there is already one"
            }
    else:
        return {"error": "Wrong analysis type ID"}


def generate_lotus2_report(
    process_id,
    input_dir,
    region,
    debug,
    analysis_type_id,
    parameters,
    is_meta=False,
):
    import os

    client = docker.from_env()

    from models.sequencing_analysis import SequencingAnalysis
    from models.sequencing_analysis_type import SequencingAnalysisType
    from models.app_configuration import AppConfiguration

    # Import MetaProject only if needed
    if is_meta:
        from models.meta_project import MetaProject

    def log(msg):
        logger.info(msg)

    # 1. FETCH DATABASE OBJECTS (Updated to handle Meta Project)
    if is_meta:
        analysis_id = SequencingAnalysis.get_by_meta_project_and_type(
            process_id, analysis_type_id
        )
    else:
        analysis_id = SequencingAnalysis.get_by_upload_and_type(
            process_id, analysis_type_id
        )
    analysis_type = SequencingAnalysisType.get(analysis_type_id)

    # Initial DB updates
    SequencingAnalysis.update_field(
        analysis_id, "lotus2_started_at", datetime.utcnow()
    )
    SequencingAnalysis.update_field(analysis_id, "lotus2_status", "Started")
    SequencingAnalysis.update_field(analysis_id, "parameters", parameters)

    # Flask-side relative path (e.g. "seq_processed/00289_.../"), captured
    # before input_dir gets rewritten below into the absolute path lotus3's
    # own container expects on its side of the mount. Used later to read
    # LotuS_progout.log back from this process (only meaningful/used for
    # non-meta runs -- see update_sequencer_read_stats_from_progout below).
    flask_relative_input_dir = input_dir

    # 2. DEFINE PATHS (Updated for Meta Projects)
    if is_meta:
        meta_data = MetaProject.get(process_id)
        # Results folder for meta projects is inside seq_processed
        input_dir = os.path.join(
            "/", "seq_processed", meta_data["results_folder"]
        )
        output_path = os.path.join(
            input_dir, "lotus2_report", analysis_type.name
        )
        # CRITICAL: For meta projects, the mapping file contains absolute paths.
        # We set the lotus3 -i parameter to / to resolve /seq_processed/...
        lotus_i_param = "/"
    else:
        # Normalize input_dir for standard projects
        input_dir = os.path.join("/", input_dir)
        output_path = os.path.join(
            input_dir, "lotus2_report", analysis_type.name
        )
        lotus_i_param = input_dir

    # Logging block
    log("Trying for:")
    for k, v in {
        "process_id": process_id,
        "analysis_type_id": analysis_type_id,
        "analysis_id": analysis_id,
        "input_dir": input_dir,
        "output_path": output_path,
        "lotus_i_param": lotus_i_param,
        "region": region,
        "debug": debug,
        "parameters": parameters,
    }.items():
        log(f" - {k}: {v}")

    debug_flag = " -v --debug " if debug == 1 else ""

    try:
        container = client.containers.get("spun-lotus3")

        # ------------------------------
        #  Helper: Run command + DB write
        # ------------------------------
        def run_lotus_command(command_list, server_size):
            command_str = " ".join(command_list)
            log(" - the command is:")
            log(command_str)

            # Store the command in DB
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_command", command_str
            )

            remote_pipeline = AppConfiguration.get_value("remote_pipeline")

            def update_read_stats():
                # Meta-projects don't own SequencingSequencerIDsTable rows
                # (they combine samples already uploaded to other
                # projects), so there's nothing to update for them.
                if is_meta:
                    return
                try:
                    update_sequencer_read_stats_from_progout(
                        process_id,
                        flask_relative_input_dir,
                        region,
                        analysis_type.name,
                    )
                except Exception:
                    # Never let a parsing hiccup here fail an otherwise
                    # successfully finished lotus2 run.
                    logger.exception(
                        "Failed to update per-sample read stats from "
                        "LotuS_progout.log for process_id=%s region=%s "
                        "analysis_type=%s",
                        process_id,
                        region,
                        analysis_type.name,
                    )

            # -------------------------------------------------------
            # REMOTE PIPELINE LOGIC
            # -------------------------------------------------------
            if str(remote_pipeline) == "1":
                log("Remote pipeline enabled → starting VM...")
                server_name = f"lotus3-{process_id}-{analysis_type_id}-{int(datetime.utcnow().timestamp())}"
                # When on the VM set temp dirs to be inside the VM.
                # Set all 3 variables because different tools use different ones.
                command_str = (
                    "export TMPDIR=/tmp/lotus_tmp && "
                    "export TMP=/tmp/lotus_tmp && "
                    "export TEMP=/tmp/lotus_tmp && "
                    "mkdir -p /tmp/lotus_tmp && " + command_str
                )

                result = run_lotus3_on_vm(
                    command_str, server_name, server_size
                )

                SequencingAnalysis.update_field(
                    analysis_id,
                    "lotus2_result",
                    result["stdout"] + "\n" + result["stderr"],
                )
                SequencingAnalysis.update_field(
                    analysis_id, "lotus2_status", "Finished"
                )
                SequencingAnalysis.update_field(
                    analysis_id, "lotus2_finished_at", datetime.utcnow()
                )
                update_read_stats()

                return

            # -------------------------------------------------------
            # NORMAL LOCAL DOCKER EXECUTION
            # -------------------------------------------------------
            result = container.exec_run(["bash", "-c", command_str])
            log(result.output)

            SequencingAnalysis.update_field(
                analysis_id, "lotus2_status", "Finished"
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_finished_at", datetime.utcnow()
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_result", result.output
            )
            update_read_stats()

        # ------------------------------
        #          REGION = ITS1/ITS2
        # ------------------------------
        if region in ["ITS1", "ITS2"]:
            server_size = "cpx62"
            mapping_file = os.path.join(
                input_dir, "mapping_files", f"{region}_Mapping.txt"
            )

            # Select SDM file
            sdm_map = {
                "sdm_miSeq_ITS_200": "/lotus2_files/sdm_miSeq_ITS_200.txt",
                "sdm_miSeq_ITS_forward": "/lotus2_files/sdm_miSeq_ITS_forward.txt",
            }
            sdmopt = sdm_map.get(
                parameters.get("sdmopt"), "/lotus2_files/sdm_miSeq_ITS.txt"
            )

            # refDB / tax4refDB selection
            if analysis_type.name in ["ITS1", "ITS2"]:
                refDB = "/lotus2_files/UNITE_v10_sh_general_release_dynamic_all_19.02.2025.fasta"
                tax4refDB = "/lotus2_files/UNITE_v10_sh_general_release_dynamic_all_19.02.2025.tax"
            else:  # eukaryome
                refDB = "/lotus2_files/mothur_EUK_ITS_v1.9.4.fasta"
                tax4refDB = "/lotus2_files/mothur_EUK_ITS_v1.9.4_lotus.tax"
                server_size = "ccx43"

            cmd = [
                "lotus3",
                debug_flag,
                "-i",
                lotus_i_param,
                "-o",
                output_path,
                "-m",
                mapping_file,
                "-refDB",
                refDB,
                "-amplicon_type",
                region,
                "-LCA_idthresh",
                "97,95,93,91,88,78",
                "-tax_group",
                "fungi",
                "-taxAligner",
                "blast",
                "-clustering",
                "vsearch",
                "-derepMin",
                "10:1,5:2,3:3",
                "-sdmThreads",
                "1",
                "-sdmopt",
                sdmopt,
                "-id",
                "0.97",
                "-tax4refDB",
                tax4refDB,
            ]
            return run_lotus_command(cmd, server_size)

        # ------------------------------
        #            REGION = SSU
        # ------------------------------
        if region == "SSU":
            parameters = parameters | analysis_type.parameters
            clustering = parameters["clustering"]
            server_size = "cpx62"

            mapping_file = os.path.join(
                input_dir, "mapping_files", "SSU_Mapping.txt"
            )

            sdm_map = {
                "sdm_miSeq2_250": "/lotus2_files/sdm_miSeq2_250.txt",
            }
            sdmopt = sdm_map.get(
                parameters.get("sdmopt"),
                "/lotus2_files/sdm_miSeq2_SSU_Spun.txt",
            )

            # Select DBs
            if analysis_type.name in ["SSU_dada2", "SSU_vsearch"]:
                # Reduced SILVA
                refDB = (
                    "/lotus2_files/vt_types_fasta_from_05-06-2019.qiime.fasta,"
                    "/lotus2_files/SLV_138.1_SSU_NO_AMF.fasta"
                )
                tax4refDB = (
                    "/lotus2_files/vt_types_GF.txt,"
                    "/lotus2_files/SLV_138.1_SSU_NO_AMF.tax"
                )

            elif analysis_type.name == "SSU_eukaryome":
                refDB = "/lotus2_files/mothur_EUK_SSU_v1.9.3.fasta"
                tax4refDB = "/lotus2_files/mothur_EUK_SSU_v1.9.3_lotus.tax"
                server_size = "ccx43"

            cmd = [
                "lotus3",
                debug_flag,
                "-i",
                lotus_i_param,
                "-o",
                output_path,
                "-m",
                mapping_file,
                "-refDB",
                refDB,
                "-tax4refDB",
                tax4refDB,
                "-amplicon_type",
                region,
                "-LCA_idthresh",
                "97,95,93,91,88,78,0",
                "-tax_group",
                "fungi",
                "-taxAligner",
                "blast",
                "-clustering",
                clustering,
                "-LCA_cover",
                "0.97",
                "-sdmThreads",
                "1",
                "-derepMin",
                "10:1,5:2,3:3",
                "-sdmopt",
                sdmopt,
            ]
            return run_lotus_command(cmd, server_size)

        # ------------------------------
        #       REGION = Full ITS
        # ------------------------------
        if region in ["Full_ITS", "Full_ITS_LSU"]:
            server_size = "cpx62"
            mapping_file = os.path.join(
                input_dir, "mapping_files", region + "_Mapping.txt"
            )
            if analysis_type.name in [
                "FULL_ITS_UNITE",
                "FULL_ITS_Eukaryome",
                "FULL_ITS_LSU_UNITE",
                "FULL_ITS_LSU_Eukaryome",
            ]:
                sdmopt = "/lotus2_files/sdm_PacBio_ITS.txt"
                platform = " -p PacBio"
                derepMin = " -derepMin 10:1,5:2,3:3 "
                LCA_cover = " -LCA_cover 0.5 "
                if analysis_type.name in [
                    "FULL_ITS_LSU_UNITE",
                    "FULL_ITS_LSU_Eukaryome",
                ]:
                    sdmopt = "/lotus2_files/sdm_PacBio_ITS_3000.txt"

                if analysis_type.name in [
                    "FULL_ITS_UNITE",
                    "FULL_ITS_LSU_UNITE",
                ]:
                    refDB = "/lotus2_files/UNITE_v10_sh_general_release_dynamic_all_19.02.2025.fasta"
                    tax4refDB = "/lotus2_files/UNITE_v10_sh_general_release_dynamic_all_19.02.2025.tax"
                else:
                    refDB = "/lotus2_files/mothur_EUK_ITS_v1.9.4.fasta"
                    tax4refDB = "/lotus2_files/mothur_EUK_ITS_v1.9.4_lotus.tax"
                cmd = [
                    "lotus3",
                    debug_flag,
                    "-i",
                    lotus_i_param,
                    "-o",
                    output_path,
                    "-m",
                    mapping_file,
                    "-refDB",
                    refDB,
                    "-tax4refDB",
                    tax4refDB,
                    "-amplicon_type",
                    "ITS",
                    "-LCA_idthresh",
                    "97,95,93,91,88,78,0",
                    "-tax_group",
                    "fungi",
                    "-taxAligner",
                    "blast",
                    "-clustering",
                    "vsearch",
                    LCA_cover,
                    "-sdmThreads",
                    "1",
                    derepMin,
                    "-sdmopt",
                    sdmopt,
                    platform,
                ]
                return run_lotus_command(cmd, server_size)

            # Unsupported Full ITS type
            SequencingAnalysis.update_field(
                analysis_id,
                "lotus2_status",
                "Abandoned. Full_ITS or Full_ITS_LSU without supported analysis.",
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_finished_at", datetime.utcnow()
            )
            log("Unsupported Full_ITS or Full_ITS_LSU analysis.")
            return

        # ------------------------------
        # UNKNOWN REGION
        # ------------------------------
        SequencingAnalysis.update_field(
            analysis_id, "lotus2_status", "Abandoned. Unknown region."
        )
        SequencingAnalysis.update_field(
            analysis_id, "lotus2_finished_at", datetime.utcnow()
        )
        log(f"Unknown region {region}")

    except Exception as e:
        logger.error(f"Error generating Lotus2 report: {str(e)}")
        SequencingAnalysis.update_field(
            analysis_id, "lotus2_status", "Error while generating."
        )
        SequencingAnalysis.update_field(
            analysis_id, "lotus2_finished_at", datetime.utcnow()
        )
        SequencingAnalysis.update_field(analysis_id, "lotus2_result", str(e))


def delete_generated_lotus2_report(
    process_id, meta_project_id, analysis_type_id
):

    if analysis_type_id != 0:
        from models.sequencing_analysis import SequencingAnalysis
        from models.sequencing_analysis_type import SequencingAnalysisType

        analysis_type = SequencingAnalysisType.get(analysis_type_id)

        if meta_project_id:
            analysis_id = SequencingAnalysis.get_by_meta_project_and_type(
                meta_project_id, analysis_type_id
            )
            from models.meta_project import MetaProject

            process_data = MetaProject.get(meta_project_id)
            input_dir = "seq_processed/" + process_data["results_folder"]
        else:
            analysis_id = SequencingAnalysis.get_by_upload_and_type(
                process_id, analysis_type_id
            )
            from models.sequencing_upload import SequencingUpload

            process_data = SequencingUpload.get(process_id)
            input_dir = "seq_processed/" + process_data["uploads_folder"]

        if analysis_id:

            SequencingAnalysis.update_field(
                analysis_id, "lotus2_celery_task_id", None
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_started_at", None
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_finished_at", None
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_command", None
            )
            SequencingAnalysis.update_field(analysis_id, "lotus2_status", None)
            SequencingAnalysis.update_field(analysis_id, "lotus2_result", None)

            output_path = input_dir + "/lotus2_report/" + analysis_type.name
            if os.path.exists(output_path) and os.path.isdir(output_path):
                shutil.rmtree(output_path)

    return {"msg": "Process initiated"}


def get_analysis_type(region):
    sequencing_analysis_type = 0
    if region == "SSU":
        sequencing_analysis_type = 1
    elif region == "ITS2":
        sequencing_analysis_type = 3
    elif region == "ITS1":
        sequencing_analysis_type = 4
    return sequencing_analysis_type


def init_generate_all_lotus2_reports(analysis_type_id, from_id, to_id):
    from tasks import generate_all_lotus2_reports_async

    generate_all_lotus2_reports_async.delay(analysis_type_id, from_id, to_id)


def generate_all_lotus2_reports(analysis_type_id, from_id, to_id):
    from models.sequencing_upload import SequencingUpload
    from models.sequencing_analysis import SequencingAnalysis

    processes_data = SequencingUpload.get_all()
    from_id = int(from_id)
    to_id = int(to_id)

    for process_data in processes_data:
        process_id = process_data["id"]
        # Check if the process_id satisfies the given conditions
        if (
            (from_id is None and to_id is None)
            or (
                from_id is not None and to_id is None and process_id >= from_id
            )
            or (from_id is None and to_id is not None and process_id <= to_id)
            or (
                from_id is not None
                and to_id is not None
                and from_id <= process_id <= to_id
            )
        ):
            for region_type, analysis_list in process_data["analysis"].items():
                for analysis in analysis_list:
                    if str(analysis_type_id) == str(
                        analysis["analysis_type_id"]
                    ):
                        # Get the fresh status from the database
                        analysis_id = SequencingAnalysis.create(
                            process_id, analysis_type_id
                        )
                        analysis = SequencingAnalysis.get(analysis_id)
                        status = analysis.lotus2_status

                        # Only proceed if the status is None
                        if status is None:
                            input_dir = (
                                "seq_processed/"
                                + process_data["uploads_folder"]
                            )
                            generate_lotus2_report(
                                process_id=process_data["id"],
                                input_dir=input_dir,
                                region=region_type,
                                debug=False,
                                analysis_type_id=analysis_type_id,
                                parameters={},
                            )
                            logger.info(
                                "inside generate_all_lotus2_reports . "
                                + " The analysis_id is "
                                + str(analysis_id)
                            )
