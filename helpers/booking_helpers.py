def select_slots(raw_slots: list) -> list:
    """
    Selects the slots to be displayed to the user.
    Fetches available slots for 14 days and chooses the first 3 days that have slots.
    Shows only one slot per day, and prefers the afternoon slots for tomorrow.
    """
    helsinki = pytz.timezone("Europe/Helsinki")
    now_hel = datetime.now(helsinki)
    today = now_hel.date()
    tomorrow = today + timedelta(days=1)
    slots_by_date = defaultdict(list)
    for slot_time in raw_slots:
        try:
            dt = dateutil.parser.isoparse(slot_time).astimezone(helsinki)
            slot_date = dt.date()
            slots_by_date[slot_date].append(dt)
        except Exception as e:
            print(f"Error parsing slot time {slot_time}: {e}")
    selected_slots = []
    used_times = set()
    for offset in range(1, 15):
        day = today + timedelta(days=offset)
        if day in slots_by_date:
            if day == tomorrow:
                afternoon_slots = [dt for dt in slots_by_date[day] if dt.hour >= 13]
                if afternoon_slots:
                    for dt in afternoon_slots:
                        tstr = dt.strftime("%H:%M")
                        if tstr not in used_times:
                            selected_slots.append(dt)
                            used_times.add(tstr)
                            break
                    else:
                        continue
                else:
                    for dt in sorted(slots_by_date[day]):
                        tstr = dt.strftime("%H:%M")
                        if tstr not in used_times:
                            selected_slots.append(dt)
                            used_times.add(tstr)
                            break
            else:
                for dt in sorted(slots_by_date[day]):
                    tstr = dt.strftime("%H:%M")
                    if tstr not in used_times:
                        selected_slots.append(dt)
                        used_times.add(tstr)
                        break
        if len(selected_slots) >= 3:
            break
    return selected_slots

def format_slots(selected_slots: list, user_lang: str) -> list:
    formatted_slots = []
    for dt in selected_slots:
        if user_lang.startswith("fi"):
            fmt = "EEEE, dd.MM. 'klo' HH:mm"
        else:
            fmt = "EEEE, dd.MM. 'at' HH:mm"
        try:
            formatted = format_datetime(dt, fmt, locale=user_lang)
        except Exception:
            formatted = dt.strftime("%A, %d.%m. at %H:%M")
        formatted_slots.append({"time": formatted, "iso": dt.isoformat()})
    return formatted_slots 