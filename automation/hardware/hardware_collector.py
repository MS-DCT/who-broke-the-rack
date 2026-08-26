import json
import ssl
import urllib.request
import base64
import getpass
import argparse
from pathlib import Path
from datetime import datetime, timezone


# =========================
# Target Server / iLO
# =========================

ILO_USER = "root"

TARGETS = {
    "server-205": {
        "ilo_ip": "192.168.0.205",
        "host": "dca-target01",
    },
    "server-207": {
        "ilo_ip": "192.168.0.207",
        "host": "dca-target02",
    },
    "server-208": {
    	"ilo_ip": "192.168.0.208",
    	"host": "dca-spare01",
    },
}

ILO_IP = None
SERVER_ID = None
HOST = None
BASE_URL = None

SYSTEM_PATH = "/redfish/v1/Systems/1/"
SMART_STORAGE_PATH = "/redfish/v1/Systems/1/SmartStorage/"
IML_ENTRIES_PATH = "/redfish/v1/Systems/1/LogServices/IML/Entries/"


# =========================
# Redfish GET
# =========================

def redfish_get(path, password):
    url = f"{BASE_URL}{path}"

    credentials = f"{ILO_USER}:{password}"
    encoded = base64.b64encode(
        credentials.encode()
    ).decode()

    request = urllib.request.Request(url)

    request.add_header(
        "Authorization",
        f"Basic {encoded}"
    )

    request.add_header(
        "Accept",
        "application/json"
    )

    context = ssl._create_unverified_context()

    with urllib.request.urlopen(
        request,
        context=context,
        timeout=5
    ) as response:

        return json.loads(
            response.read().decode()
        )


# =========================
# Result Conversion
# =========================

def health_result(health, state=None):

    if health is None:
        return "UNKNOWN"

    health_upper = str(health).upper()

    if health_upper == "OK":

        if state is None:
            return "PASS"

        state_upper = str(state).upper()

        if state_upper == "ENABLED":
            return "PASS"

        if state_upper in [
            "DISABLED",
            "ABSENT",
            "OFFLINE"
        ]:
            return "FAIL"

        return "WARN"

    if health_upper in [
        "WARNING",
        "DEGRADED"
    ]:
        return "WARN"

    if health_upper in [
        "CRITICAL",
        "FAILED",
        "FAIL"
    ]:
        return "FAIL"

    return "UNKNOWN"


def power_result(power_state):

    if power_state is None:
        return "UNKNOWN"

    state = str(power_state).upper()

    if state == "ON":
        return "PASS"

    if state == "OFF":
        return "WARN"

    return "UNKNOWN"


def post_result(post_state):

    if post_state is None:
        return "UNKNOWN"

    state = str(post_state).upper()

    if state == "FINISHEDPOST":
        return "PASS"

    if state in [
        "INPOST",
        "INPOSTDISCOVERYCOMPLETE"
    ]:
        return "WARN"

    if state == "POWEROFF":
        return "SKIP"

    return "UNKNOWN"


# =========================
# Evidence Helper
# =========================

def make_evidence(
    result,
    value,
    detail,
    source
):

    return {
        "result": result,
        "value": value,
        "detail": detail,
        "source": source
    }


# =========================
# Collection Helper
# =========================

def get_member_paths(collection):

    paths = []

    for member in collection.get(
        "Members",
        []
    ):
        path = (
            member.get("@odata.id")
            or member.get("href")
        )

        if path:
            paths.append(path)

    return paths


# =========================
# Main Collector
# =========================

def main():

    global ILO_IP, SERVER_ID, HOST, BASE_URL

    parser = argparse.ArgumentParser(
        description="Collect Redfish-based hardware evidence."
    )
    parser.add_argument(
        "--server-id",
        choices=TARGETS.keys(),
        default="server-205",
        help="Target server ID"
    )
    parser.add_argument(
        "--incident-id",
        default=None,
        help="Incident ID passed by Incident Controller/C"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON output path"
    )
    args = parser.parse_args()

    target = TARGETS[args.server_id]

    SERVER_ID = args.server_id
    HOST = target["host"]
    ILO_IP = target["ilo_ip"]
    BASE_URL = f"https://{ILO_IP}"

    password = getpass.getpass(
        "iLO password: "
    )

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    output = {
        "incident_id": args.incident_id,
        "server_id": SERVER_ID,
        "host": HOST,
        "timestamp": timestamp,
        "category": "hardware",
        "source": "redfish",
        "evidence": {},
        "iml_events": []
    }

    evidence = output["evidence"]

    # -------------------------
    # 1. iLO Reachability
    # -------------------------

    try:

        system = redfish_get(
            SYSTEM_PATH,
            password
        )

        evidence[
            "ilo_reachability"
        ] = make_evidence(
            "PASS",
            "REACHABLE",
            f"iLO {ILO_IP} Redfish API access confirmed",
            SYSTEM_PATH
        )

    except Exception as e:

        evidence[
            "ilo_reachability"
        ] = make_evidence(
            "FAIL",
            "UNREACHABLE",
            str(e),
            SYSTEM_PATH
        )

        print(
            json.dumps(
                output,
                indent=2,
                ensure_ascii=False
            )
        )

        return


    # -------------------------
    # 2. Power State
    # -------------------------

    power_state = system.get(
        "PowerState"
    )

    evidence[
        "power_state"
    ] = make_evidence(
        power_result(power_state),
        power_state or "UNKNOWN",
        f"PowerState={power_state}",
        SYSTEM_PATH
    )


    # -------------------------
    # 3. System Health
    # -------------------------

    system_status = system.get(
        "Status",
        {}
    )

    system_health = system_status.get(
        "Health"
    )

    system_state = system_status.get(
        "State"
    )

    evidence[
        "system_health"
    ] = make_evidence(
        health_result(
            system_health,
            system_state
        ),
        system_health or "UNKNOWN",
        (
            f"Health={system_health}, "
            f"State={system_state}"
        ),
        SYSTEM_PATH
    )


    # -------------------------
    # 4. POST State
    # -------------------------

    post_state = (
        system.get("Oem", {})
        .get("Hp", {})
        .get("PostState")
    )

    evidence[
        "post_state"
    ] = make_evidence(
        post_result(post_state),
        post_state or "UNKNOWN",
        (
            "POST completed successfully"
            if post_state == "FinishedPost"
            else f"PostState={post_state}"
        ),
        "/redfish/v1/Systems/1/Oem/Hp/PostState"
    )


    # -------------------------
    # 5. Boot / OS Access State
    # -------------------------

    host_correlation = system.get(
        "HostCorrelation",
        {}
    )

    host_ips = [
        ip
        for ip in host_correlation.get("IPAddress", [])
        if ip
    ]

    if host_ips:
        boot_os_result = "UNKNOWN"
        boot_os_value = "HOST_IP_REPORTED"
        boot_os_detail = (
            "POST completed; iLO reported host IP(s): "
            + ", ".join(host_ips)
            + ". OS reachability still requires a separate network/OS probe."
        )
    else:
        boot_os_result = "UNKNOWN"
        boot_os_value = "NOT_VERIFIED"
        boot_os_detail = (
            "POST state collected, but Redfish HostCorrelation does not provide "
            "a usable OS IP address. OS reachability requires a separate "
            "network/OS probe."
        )

    evidence[
        "boot_os_state"
    ] = make_evidence(
        boot_os_result,
        boot_os_value,
        boot_os_detail,
        SYSTEM_PATH
    )


    # -------------------------
    # 6. Memory Health
    # -------------------------

    memory = (
        system.get("Memory")
        or system.get("MemorySummary")
        or {}
    )

    memory_status = memory.get(
        "Status",
        {}
    )

    memory_health = memory_status.get(
        "HealthRollUp"
    ) or memory_status.get(
        "Health"
    )

    total_memory = (
        memory.get("TotalSystemMemoryGiB")
	or system.get("MemorySummary", {}).get("TotalSystemMemoryGiB")
        or system.get("TotalSystemMemoryGiB")
    )

    evidence[
        "memory_health"
    ] = make_evidence(
        health_result(
            memory_health
        ),
        memory_health or "UNKNOWN",
        (
            f"Health={memory_health}, "
            f"TotalMemory={total_memory} GiB"
        ),
        SYSTEM_PATH
    )


    # -------------------------
    # 7. SmartStorage
    # -------------------------

    try:

        smart_storage = redfish_get(
            SMART_STORAGE_PATH,
            password
        )

        storage_status = (
            smart_storage.get(
                "Status",
                {}
            )
        )

        storage_health = (
            storage_status.get(
                "Health"
            )
        )

        storage_state = (
            storage_status.get(
                "State"
            )
        )

        evidence[
            "storage_health"
        ] = make_evidence(
            health_result(
                storage_health,
                storage_state
            ),
            storage_health or "UNKNOWN",
            (
                f"Health={storage_health}, "
                f"State={storage_state}"
            ),
            SMART_STORAGE_PATH
        )

    except Exception as e:

        evidence[
            "storage_health"
        ] = make_evidence(
            "UNKNOWN",
            "UNAVAILABLE",
            str(e),
            SMART_STORAGE_PATH
        )

        smart_storage = {}


    # -------------------------
    # 8. Array Controllers
    # -------------------------

    controller_path = (
        smart_storage
        .get("links", {})
        .get("ArrayControllers", {})
        .get("href")
    )

    if controller_path:

        try:

            controllers = redfish_get(
                controller_path,
                password
            )

            controller_members = (
                get_member_paths(
                    controllers
                )
            )

            if not controller_members:

                evidence[
                    "controller_health"
                ] = make_evidence(
                    "UNKNOWN",
                    "NOT_FOUND",
                    "No SmartStorage array controller found",
                    controller_path
                )

            for index, path in enumerate(
                controller_members
            ):

                controller = redfish_get(
                    path,
                    password
                )

                status = controller.get(
                    "Status",
                    {}
                )

                health = status.get(
                    "Health"
                )

                state = status.get(
                    "State"
                )

                model = controller.get(
                    "Model",
                    "UNKNOWN"
                )

                evidence[
                    f"controller_{index}_health"
                ] = make_evidence(
                    health_result(
                        health,
                        state
                    ),
                    health or "UNKNOWN",
                    (
                        f"Model={model}, "
                        f"Health={health}, "
                        f"State={state}"
                    ),
                    path
                )


                # -----------------
                # Logical Drives
                # -----------------

                logical_path = (
                    controller
                    .get("links", {})
                    .get("LogicalDrives", {})
                    .get("href")
                )

                if logical_path:

                    logical_collection = (
                        redfish_get(
                            logical_path,
                            password
                        )
                    )

                    logical_members = (
                        get_member_paths(
                            logical_collection
                        )
                    )

                    for drive_index, drive_path in enumerate(
                        logical_members
                    ):

                        drive = redfish_get(
                            drive_path,
                            password
                        )

                        drive_status = (
                            drive.get(
                                "Status",
                                {}
                            )
                        )

                        drive_health = (
                            drive_status.get(
                                "Health"
                            )
                        )

                        drive_state = (
                            drive_status.get(
                                "State"
                            )
                        )

                        raid = drive.get(
                            "Raid",
                            "UNKNOWN"
                        )

                        capacity = drive.get(
                            "CapacityMiB",
                            "UNKNOWN"
                        )

                        evidence[
                            f"logical_drive_{drive_index}_health"
                        ] = make_evidence(
                            health_result(
                                drive_health,
                                drive_state
                            ),
                            drive_health or "UNKNOWN",
                            (
                                f"RAID={raid}, "
                                f"CapacityMiB={capacity}, "
                                f"Health={drive_health}, "
                                f"State={drive_state}"
                            ),
                            drive_path
                        )


                # -----------------
                # Physical Drives
                # -----------------

                disk_path = (
                    controller
                    .get("links", {})
                    .get("PhysicalDrives", {})
                    .get("href")
                )

                if disk_path:

                    disk_collection = (
                        redfish_get(
                            disk_path,
                            password
                        )
                    )

                    disk_members = (
                        get_member_paths(
                            disk_collection
                        )
                    )

                    for disk_index, physical_path in enumerate(
                        disk_members
                    ):

                        disk = redfish_get(
                            physical_path,
                            password
                        )

                        disk_status = disk.get(
                            "Status",
                            {}
                        )

                        disk_health = (
                            disk_status.get(
                                "Health"
                            )
                        )

                        disk_state = (
                            disk_status.get(
                                "State"
                            )
                        )

                        model = disk.get(
                            "Model",
                            "UNKNOWN"
                        )

                        media_type = disk.get(
                            "MediaType",
                            "UNKNOWN"
                        )

                        interface_type = disk.get(
                            "InterfaceType",
                            "UNKNOWN"
                        )

                        capacity_gb = disk.get(
                            "CapacityGB",
                            "UNKNOWN"
                        )

                        location = disk.get(
                            "Location",
                            "UNKNOWN"
                        )

                        evidence[
                            f"physical_drive_{disk_index}_health"
                        ] = make_evidence(
                            health_result(
                                disk_health,
                                disk_state
                            ),
                            disk_health or "UNKNOWN",
                            (
                                f"Model={model}, "
                                f"MediaType={media_type}, "
                                f"Interface={interface_type}, "
                                f"CapacityGB={capacity_gb}, "
                                f"Location={location}, "
                                f"Health={disk_health}, "
                                f"State={disk_state}"
                            ),
                            physical_path
                        )

        except Exception as e:

            evidence[
                "controller_collection"
            ] = make_evidence(
                "UNKNOWN",
                "COLLECTION_ERROR",
                str(e),
                controller_path
            )

    else:

        evidence[
            "controller_health"
        ] = make_evidence(
            "UNKNOWN",
            "ENDPOINT_NOT_FOUND",
            "ArrayControllers endpoint not found",
            SMART_STORAGE_PATH
        )


    # -------------------------
    # 9. IML Events
    # -------------------------

    try:

        iml_collection = redfish_get(
            IML_ENTRIES_PATH,
            password
        )

        iml_items = (
            iml_collection.get("Items")
            or iml_collection.get("Members")
            or []
        )

        for item in iml_items:

            if (
                isinstance(item, dict)
                and (
                    "Message" not in item
                    or "Severity" not in item
                    or "Created" not in item
                )
            ):
                item_path = (
                    item.get("@odata.id")
                    or item.get("href")
                )

                if item_path:
                    try:
                        item = redfish_get(
                            item_path,
                            password
                        )
                    except Exception:
                        continue

            if not isinstance(item, dict):
                continue

            output["iml_events"].append({
                "message": item.get(
                    "Message",
                    ""
                ),
                "severity": item.get(
                    "Severity",
                    "UNKNOWN"
                ),
                "created": item.get(
                    "Created",
                    ""
                ),
                "subsystem": "unknown"
            })

    except Exception:
        # IML is historical/context evidence only.
        # Failure to collect it must not change current Hardware Health results.
        output["iml_events"] = []


    # -------------------------
    # Final JSON
    # -------------------------

    json_text = json.dumps(
        output,
        indent=2,
        ensure_ascii=False
    )

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (
            Path(__file__).resolve().parents[2]
            / "evidence"
            / "day2"
            / "hardware"
            / f"{HOST}.json"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        json_text + "\n",
        encoding="utf-8"
    )

    print(json_text)
    print(
        f"\nJSON saved to: "
        f"{output_path}"
    )


if __name__ == "__main__":
    main()
