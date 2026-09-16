import asyncio
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from telethon import TelegramClient
from telethon.errors import ChatAdminRequiredError
from telethon.tl.types import Channel, Chat

from config import API_ID, API_HASH, SESSION_NAME


TEHRAN_TZ = ZoneInfo("Asia/Tehran")
BACK_COMMAND = "back"


def to_tehran(message_date):
    if message_date is None:
        return None

    if message_date.tzinfo is None:
        message_date = message_date.replace(tzinfo=timezone.utc)

    return message_date.astimezone(TEHRAN_TZ)


def format_tehran(message_date):
    iran_date = to_tehran(message_date)

    if iran_date is None:
        return "NO DATE"

    return iran_date.strftime("%Y-%m-%d %H:%M:%S")


def parse_local_datetime(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def get_message_date(message):
    message_date = getattr(message, "date", None)

    if message_date is None:
        return None

    if message_date.tzinfo is None:
        message_date = message_date.replace(tzinfo=timezone.utc)

    return message_date


def is_real_message(message):
    return type(message).__name__ != "MessageService"


def get_system_offset():
    now_local = datetime.now().astimezone()

    local_offset = now_local.utcoffset()

    if local_offset is None:
        local_offset = timedelta(0)

    iran_offset = datetime.now(TEHRAN_TZ).utcoffset()

    if iran_offset is None:
        iran_offset = timedelta(0)

    return local_offset - iran_offset


def convert_local_to_iran(local_datetime, system_offset):
    return (local_datetime - system_offset).replace(
        tzinfo=TEHRAN_TZ
    )


def print_back_hint():
    print("Type 'back' to return to the previous step.")


async def get_real_target(client, entity):
    migrated_to = getattr(entity, "migrated_to", None)

    if migrated_to is not None:
        print("\nGroup-e entekhab shode migrate shode ast.")

        channel_id = getattr(
            migrated_to,
            "channel_id",
            None
        )

        print(f"Supergroup ID: {channel_id}")

        new_entity = await client.get_entity(
            migrated_to
        )

        print(
            f"Supergroup Name: "
            f"{getattr(new_entity, 'title', 'Bedoon Name')}"
        )

        print(
            f"Supergroup Type: "
            f"{type(new_entity).__name__}"
        )

        return new_entity

    return entity


async def get_latest_real_message(client, target):
    async for message in client.iter_messages(
        target,
        limit=100
    ):
        if not is_real_message(message):
            continue

        if get_message_date(message) is None:
            continue

        return message

    return None


async def collect_messages_in_range(
    client,
    target,
    start_iran,
    end_iran
):
    selected_messages = []

    async for message in client.iter_messages(target):
        if not is_real_message(message):
            continue

        message_date = get_message_date(message)

        if message_date is None:
            continue

        iran_date = to_tehran(message_date)

        if iran_date < start_iran:
            break

        if start_iran <= iran_date <= end_iran:
            selected_messages.append(message)

    selected_messages.reverse()

    return selected_messages


def parse_id_list(value):
    parts = value.split(",")

    ids = []

    for part in parts:
        part = part.strip()

        if not part:
            continue

        try:
            message_id = int(part)
        except ValueError:
            return None

        if message_id <= 0:
            return None

        ids.append(message_id)

    if not ids:
        return None

    return ids


def select_messages_by_ids(messages, requested_ids):
    requested_ids = set(requested_ids)

    return [
        message
        for message in messages
        if message.id in requested_ids
    ]


def show_selected_messages(messages):
    print("\n" + "=" * 70)
    print("              SELECTED MESSAGES")
    print("=" * 70)

    print(f"Tedad payam: {len(messages)}")

    preview_count = min(10, len(messages))

    print("\nChand payam-e entekhab shode:")

    for message in messages[:preview_count]:
        print(
            f"ID: {message.id} | "
            f"Date Iran: "
            f"{format_tehran(get_message_date(message))}"
        )

    if len(messages) > preview_count:
        print(
            f"... va {len(messages) - preview_count} payam-e digar."
        )


def get_action_name(operation):
    if operation == "d":
        return "Delete"

    if operation == "f":
        return "Forward"

    return "Forward Hide Sender Name"


async def delete_messages(
    client,
    target,
    selected_messages
):
    print("\n" + "=" * 70)
    print("              DELETE")
    print("=" * 70)

    message_ids = [
        message.id
        for message in selected_messages
    ]

    batch_size = 100
    deleted_count = 0

    for index in range(
        0,
        len(message_ids),
        batch_size
    ):
        batch = message_ids[
            index:index + batch_size
        ]

        try:
            await client.delete_messages(
                target,
                batch
            )

            deleted_count += len(batch)

            print(
                f"Hazf shod: "
                f"{deleted_count}/{len(message_ids)}"
            )

        except ChatAdminRequiredError:
            print("\nHoghogh-e hazf payam nadarid.")
            print(
                "Amaliat dar haminja motavaqef shod."
            )
            return False

        except Exception as error:
            print("\nKhataye hazf:")
            print(
                f"Error Type: "
                f"{type(error).__name__}"
            )
            print(f"Error: {error}")
            return False

    print("\n" + "=" * 70)
    print("              FINISHED")
    print("=" * 70)

    print(
        f"Tedad payamhaye hazf shode: "
        f"{deleted_count}"
    )

    return True


async def forward_messages(
    client,
    target,
    selected_messages,
    destination_id
):
    print("\n" + "=" * 70)
    print("              FORWARD")
    print("=" * 70)

    try:
        destination = await client.get_entity(
            destination_id
        )
    except Exception as error:
        print("\nMagsad peyda nashod.")
        print(
            f"Error Type: "
            f"{type(error).__name__}"
        )
        print(f"Error: {error}")
        return False

    message_ids = [
        message.id
        for message in selected_messages
    ]

    batch_size = 100
    forwarded_count = 0

    for index in range(
        0,
        len(message_ids),
        batch_size
    ):
        batch = message_ids[
            index:index + batch_size
        ]

        try:
            await client.forward_messages(
                destination,
                batch,
                from_peer=target
            )

            forwarded_count += len(batch)

            print(
                f"Forward shod: "
                f"{forwarded_count}/{len(message_ids)}"
            )

        except Exception as error:
            print("\nKhataye Forward:")
            print(
                f"Error Type: "
                f"{type(error).__name__}"
            )
            print(f"Error: {error}")
            return False

    print("\n" + "=" * 70)
    print("              FINISHED")
    print("=" * 70)

    print(
        f"Tedad payamhaye Forward shode: "
        f"{forwarded_count}"
    )

    return True


async def forward_hidden_sender(
    client,
    target,
    selected_messages,
    destination_id
):
    print("\n" + "=" * 70)
    print("        FORWARD - HIDE SENDER NAME")
    print("=" * 70)

    try:
        destination = await client.get_entity(
            destination_id
        )
    except Exception as error:
        print("\nMagsad peyda nashod.")
        print(
            f"Error Type: "
            f"{type(error).__name__}"
        )
        print(f"Error: {error}")
        return False

    sent_count = 0

    for message in selected_messages:
        try:
            message_text = getattr(
                message,
                "message",
                None
            )

            if message.media:
                await client.send_file(
                    destination,
                    message.media,
                    caption=message_text or ""
                )

            elif message_text:
                await client.send_message(
                    destination,
                    message_text
                )

            else:
                print(
                    f"Payam ID {message.id} "
                    f"format-e ersal shodani nadarad."
                )
                continue

            sent_count += 1

            print(
                f"Forward Hide Sender shod: "
                f"{sent_count}/{len(selected_messages)}"
            )

        except Exception as error:
            print(
                f"\nKhataye ersal payam "
                f"ID {message.id}:"
            )
            print(
                f"Error Type: "
                f"{type(error).__name__}"
            )
            print(f"Error: {error}")
            return False

    print("\n" + "=" * 70)
    print("              FINISHED")
    print("=" * 70)

    print(
        f"Tedad payamhaye ersal shode: "
        f"{sent_count}"
    )

    return True


async def choose_operation():
    while True:
        print("\n" + "=" * 70)
        print("              OPERATION")
        print("=" * 70)

        print(
            'Delete / Forward / '
            'Forward "Hide Sender Name"'
        )

        print(
            "d = Delete"
        )

        print(
            "f = Forward"
        )

        print(
            "fh = Forward Hide Sender Name"
        )

        print(
            "back = Return to previous step"
        )

        value = input(
            "\nEnter operation (d/f/fh/back): "
        ).strip().lower()

        if value in ("d", "f", "fh"):
            return value

        if value == BACK_COMMAND:
            return BACK_COMMAND

        print(
            "Lotfan d, f, fh ya back vared konid."
        )


async def choose_group(dialogs):
    while True:
        print("\n" + "=" * 70)
        print("              GROUP VA CHANNEL")
        print("=" * 70)

        for index, item in enumerate(
            dialogs,
            start=1
        ):
            print(
                f"{index}. "
                f"{item['name']} | "
                f"{item['type']} | "
                f"{item['id']}"
            )

        print("=" * 70)

        print_back_hint()

        value = input(
            "\nShomare ra vared konid: "
        ).strip().lower()

        if value == BACK_COMMAND:
            return BACK_COMMAND

        try:
            number = int(value)
        except ValueError:
            print("Faghat adad ya back vared konid.")
            continue

        if number < 1 or number > len(dialogs):
            print("Shomare eshtebah ast.")
            continue

        return dialogs[number - 1]


async def choose_start_time(system_offset):
    while True:
        print("\n" + "=" * 70)
        print("              START TIME")
        print("=" * 70)

        print(
            "Format: YYYY-MM-DD HH:MM"
        )

        print_back_hint()

        value = input(
            "\nStart time: "
        ).strip()

        if value.lower() == BACK_COMMAND:
            return BACK_COMMAND

        start_local = parse_local_datetime(value)

        if start_local is None:
            print("Format eshtebah ast.")
            continue

        start_iran = convert_local_to_iran(
            start_local,
            system_offset
        )

        return start_local, start_iran


async def choose_end_time(
    start_local,
    start_iran,
    latest_iran,
    system_offset
):
    while True:
        print("\n" + "=" * 70)
        print("              END TIME")
        print("=" * 70)

        print(
            "Format: YYYY-MM-DD HH:MM"
        )

        print(
            "Khali = ta akharin payam-e asli"
        )

        print_back_hint()

        value = input(
            "\nEnd time: "
        ).strip()

        if value.lower() == BACK_COMMAND:
            return BACK_COMMAND

        if value == "":
            return (
                start_iran,
                latest_iran
            )

        end_local = parse_local_datetime(value)

        if end_local is None:
            print("Format eshtebah ast.")
            continue

        if end_local < start_local:
            print(
                "End time nemitavanad "
                "az Start time zoodtar bashad."
            )
            continue

        end_iran = convert_local_to_iran(
            end_local,
            system_offset
        )

        end_iran = end_iran.replace(
            second=59,
            microsecond=999999
        )

        return start_iran, end_iran


async def choose_message_selection(
    messages_in_range
):
    while True:
        print("\n" + "=" * 70)
        print("              MESSAGE SELECTION")
        print("=" * 70)

        print("1. Hame payamha")
        print("2. Yek ID")
        print("3. ID haye khas")
        print("back = Return to previous step")

        choice = input(
            "\nEntekhab konid (1/2/3/back): "
        ).strip().lower()

        if choice == BACK_COMMAND:
            return BACK_COMMAND

        if choice not in ("1", "2", "3"):
            print(
                "Entekhab eshtebah ast."
            )
            continue

        if choice == "1":
            return messages_in_range

        if choice == "2":
            while True:
                print_back_hint()

                value = input(
                    "\nID payam ra vared konid: "
                ).strip().lower()

                if value == BACK_COMMAND:
                    break

                ids = parse_id_list(value)

                if ids is None or len(ids) != 1:
                    print(
                        "Lotfan faghat yek ID "
                        "adadi vared konid."
                    )
                    continue

                selected = select_messages_by_ids(
                    messages_in_range,
                    ids
                )

                if not selected:
                    print(
                        "In ID dar bazeh entekhab shode "
                        "peyada nashod."
                    )
                    continue

                return selected

            continue

        while True:
            print_back_hint()

            value = input(
                "\nID ha ra ba comma vared konid: "
            ).strip().lower()

            if value == BACK_COMMAND:
                break

            ids = parse_id_list(value)

            if ids is None:
                print(
                    "ID ha bayad adadi bashand "
                    "va ba comma joda shavand."
                )
                continue

            selected = select_messages_by_ids(
                messages_in_range,
                ids
            )

            if not selected:
                print(
                    "Hich kodam az ID ha dar bazeh "
                    "entekhab shode peyda nashod."
                )
                continue

            return selected


async def choose_destination():
    while True:
        print("\n" + "=" * 70)
        print("              FORWARD DESTINATION")
        print("=" * 70)

        print_back_hint()

        value = input(
            "\nID magsad-e Forward ra vared konid: "
        ).strip().lower()

        if value == BACK_COMMAND:
            return BACK_COMMAND

        try:
            destination_id = int(value)

            if destination_id <= 0:
                print(
                    "ID bayad adad-e mosbat bashad."
                )
                continue

            return destination_id

        except ValueError:
            print(
                "ID bayad adadi bashad."
            )


async def confirm_action(
    operation,
    selected_messages,
    destination_id
):
    while True:
        print("\n" + "=" * 70)
        print("              FINAL REVIEW")
        print("=" * 70)

        print(
            f"Operation: "
            f"{get_action_name(operation)}"
        )

        print(
            f"Tedad payam: "
            f"{len(selected_messages)}"
        )

        if operation in ("f", "fh"):
            print(
                f"Destination ID: "
                f"{destination_id}"
            )

        print("\ny = Proceed")
        print("s = Cancel")
        print("back = Return to previous step")

        value = input(
            "\nEnter y/s/back: "
        ).strip().lower()

        if value in ("y", "s", BACK_COMMAND):
            return value

        print(
            "Lotfan y, s ya back vared konid."
        )


async def run_operation_flow(
    client,
    target,
    latest_message,
    operation
):
    latest_date = get_message_date(
        latest_message
    )

    latest_iran = to_tehran(
        latest_date
    )

    system_now = datetime.now().astimezone()

    system_timezone = (
        system_now.tzname()
        or "Unknown"
    )

    system_offset = get_system_offset()

    iran_now = datetime.now(
        TEHRAN_TZ
    )

    while True:
        print("\n" + "=" * 70)
        print("              SYSTEM TIME")
        print("=" * 70)

        print(
            f"System Time: "
            f"{system_now.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        print(
            f"System Timezone: "
            f"{system_timezone}"
        )

        print(
            f"Iran Time: "
            f"{iran_now.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        total_offset_minutes = int(
            system_offset.total_seconds() // 60
        )

        sign = (
            "+"
            if total_offset_minutes >= 0
            else "-"
        )

        absolute_offset = abs(
            total_offset_minutes
        )

        offset_hours = absolute_offset // 60
        offset_minutes = absolute_offset % 60

        print(
            f"System nesbat be Iran: "
            f"{sign}{offset_hours:02d}:"
            f"{offset_minutes:02d}"
        )

        start_result = await choose_start_time(
            system_offset
        )

        if start_result == BACK_COMMAND:
            return "back"

        start_local, start_iran = start_result

        while True:
            end_result = await choose_end_time(
                start_local,
                start_iran,
                latest_iran,
                system_offset
            )

            if end_result == BACK_COMMAND:
                break

            start_iran, end_iran = end_result

            print("\n" + "=" * 70)
            print("              CONVERTED RANGE")
            print("=" * 70)

            print(
                f"Start Iran: "
                f"{start_iran.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            print(
                f"End Iran: "
                f"{end_iran.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            print(
                "\nDar hale peyda kardan "
                "payamhaye in bazeh..."
            )

            messages_in_range = (
                await collect_messages_in_range(
                    client,
                    target,
                    start_iran,
                    end_iran
                )
            )

            if not messages_in_range:
                print(
                    "\nHich payami dar in bazeh peyda nashod."
                )
                break

            while True:
                selected_messages = (
                    await choose_message_selection(
                        messages_in_range
                    )
                )

                if selected_messages == BACK_COMMAND:
                    break

                if not selected_messages:
                    print(
                        "\nHich payami entekhab nashod."
                    )
                    continue

                show_selected_messages(
                    selected_messages
                )

                destination_id = None

                if operation in ("f", "fh"):
                    while True:
                        destination_result = (
                            await choose_destination()
                        )

                        if (
                            destination_result
                            == BACK_COMMAND
                        ):
                            break

                        destination_id = (
                            destination_result
                        )

                        break

                    if destination_id == BACK_COMMAND:
                        continue

                while True:
                    confirmation = (
                        await confirm_action(
                            operation,
                            selected_messages,
                            destination_id
                        )
                    )

                    if confirmation == BACK_COMMAND:
                        if operation in ("f", "fh"):
                            break

                        break

                    if confirmation == "s":
                        print(
                            "\nAmaliat cancel shod."
                        )
                        return "cancel"

                    if confirmation == "y":
                        if operation == "d":
                            await delete_messages(
                                client,
                                target,
                                selected_messages
                            )

                        elif operation == "f":
                            await forward_messages(
                                client,
                                target,
                                selected_messages,
                                destination_id
                            )

                        else:
                            await forward_hidden_sender(
                                client,
                                target,
                                selected_messages,
                                destination_id
                            )

                        return "done"

                if confirmation == BACK_COMMAND:
                    continue

            if selected_messages == BACK_COMMAND:
                continue

            break

    return "back"


async def main():
    print("=" * 70)
    print("              TELEGRAM MESSAGE TOOL")
    print("=" * 70)

    client = TelegramClient(
        SESSION_NAME,
        API_ID,
        API_HASH
    )

    try:
        await client.start()

        print("\nConnect shod.")

        dialogs = []

        async for dialog in client.iter_dialogs():
            entity = dialog.entity

            if isinstance(entity, Channel):
                if getattr(
                    entity,
                    "broadcast",
                    False
                ):
                    entity_type = "Channel"
                else:
                    entity_type = "Supergroup"

            elif isinstance(entity, Chat):
                entity_type = "Basic Group"

            else:
                continue

            dialogs.append(
                {
                    "entity": entity,
                    "name": (
                        dialog.name
                        or "Bedoon Name"
                    ),
                    "type": entity_type,
                    "id": entity.id
                }
            )

        if not dialogs:
            print(
                "\nHich group ya channel peyda nashod."
            )
            return

        current_dialog_index = 0

        while True:
            selected = await choose_group(
                dialogs
            )

            if selected == BACK_COMMAND:
                print(
                    "\nAz barname kharej shod."
                )
                return

            entity = selected["entity"]

            print("\n" + "=" * 70)
            print("              SELECTED CHAT")
            print("=" * 70)

            print(
                f"Name: {selected['name']}"
            )

            print(
                f"Type: {selected['type']}"
            )

            print(
                f"ID: {selected['id']}"
            )

            print(
                f"Python Type: "
                f"{type(entity).__name__}"
            )

            target = await get_real_target(
                client,
                entity
            )

            print("\n" + "=" * 70)
            print("              REAL TARGET")
            print("=" * 70)

            print(
                f"Name: "
                f"{getattr(target, 'title', None)}"
            )

            print(
                f"ID: "
                f"{getattr(target, 'id', None)}"
            )

            print(
                f"Python Type: "
                f"{type(target).__name__}"
            )

            print(
                "\nDar hale peyda kardan "
                "akharin payam-e asli..."
            )

            latest_message = (
                await get_latest_real_message(
                    client,
                    target
                )
            )

            if latest_message is None:
                print(
                    "\nHich payam-e asli peyda nashod."
                )
                return

            print("\n" + "=" * 70)
            print("              LAST REAL MESSAGE")
            print("=" * 70)

            print(
                f"Message ID: "
                f"{latest_message.id}"
            )

            latest_date = get_message_date(
                latest_message
            )

            latest_iran = to_tehran(
                latest_date
            )

            print(
                f"Date Iran: "
                f"{latest_iran.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            latest_text = getattr(
                latest_message,
                "message",
                None
            )

            print("\nMatn-e payam:")

            if latest_text:
                print(latest_text)
            else:
                print("[BEDOON MATN]")

            while True:
                operation = await choose_operation()

                if operation == BACK_COMMAND:
                    break

                result = await run_operation_flow(
                    client,
                    target,
                    latest_message,
                    operation
                )

                if result == "back":
                    continue

                if result in ("done", "cancel"):
                    return

    except Exception as error:
        print("\n" + "=" * 70)
        print("              MAIN ERROR")
        print("=" * 70)

        print(
            f"Error Type: "
            f"{type(error).__name__}"
        )

        print(
            f"Error: {error}"
        )

    finally:
        if client.is_connected():
            await client.disconnect()

            print(
                "\nAz Telegram disconnect shod."
            )


if __name__ == "__main__":
    asyncio.run(main())