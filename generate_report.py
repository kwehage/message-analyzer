#!/usr/bin/env python

import csv
import time
import math
import matplotlib.pyplot as plt
import argparse
from pathlib import Path
from operator import itemgetter
from email.parser import Parser
import re
import datetime
import subprocess
import shutil
import magic


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a PDF report and plots from a decrypted signal "
                    "backup and email messages")
    parser.add_argument(
        "--sms-backup-file", "-S", required=True,
        help="Signal backup file in sms/csv format")
    parser.add_argument(
        "--address", "-A", required=False,
        help="Numeric ID for sms message", default=None)
    parser.add_argument(
        "--mms-backup-file", "-M", required=True,
        help="Signal backup file in sms/csv format")
    parser.add_argument(
        "--email-directory", "-E", required=True,
        help="Folder containing email messages")
    parser.add_argument(
        "--media-directory", "-I", required=True,
        help="Folder containing media files")
    parser.add_argument(
        "--name", "-N", required=False,
        help="Name of person to use in report",
        default=None)
    parser.add_argument(
        "--output-directory", "-O", required=False,
        help="Directory to store output plots and summary report",
        default=".")
    parser.add_argument(
        "--date", "-D", required=False,
        help="Show only messages after date", default=None)
    parser.add_argument(
        "--output-file", "-F", required=False,
        help="Report filename", default="report.md")
    return parser.parse_args()


def get_media(args, msgs):
    media_dir = Path(args.media_directory)
    report_dir = Path(args.output_directory)
    report_dir.mkdir(exist_ok=True)
    media_save_dir = report_dir / media_dir.name
    media_save_dir.mkdir(exist_ok=True)

    tol = 7000  # milliseconds
    if not media_dir.exists() or not media_dir.is_dir():
        raise Exception("Media path {args.media_directory} does not exist")
    for file_ in media_dir.iterdir():
        timestamp = file_.stem
        for msg in msgs:
            if math.fabs(msg["time_sent_int"] - int(timestamp)) < tol:
                if "media" not in msg:
                    msg["media"] = []
                ext = file_.suffix
                if ext == ".unknown":
                    filetype = magic.from_file(str(file_), mime=True)
                    if filetype is not None:
                        ext = "." + filetype.split("/")[1]
                msg["media"].append(str(file_.parent / file_.stem) + ext)
                print(
                    f"copying: {file_} to "
                    f"{media_save_dir / (file_.stem + ext)}")
                shutil.copy(file_, media_save_dir / (file_.stem + ext))
    for msg in msgs:
        if "media" not in msg:
            print(f"No media found for msg {msg['time_sent_int']}")


def sort_msgs(msgs):
    return sorted(msgs, key=itemgetter('time_sent_int'))


def load_sms_data(args):
    reader = \
        csv.reader(open(args.sms_backup_file, newline=""),
                   skipinitialspace=True)
    # skip header
    next(reader, None)
    time_received_col = 6
    msg_body_col = 15
    address_col = 2

    msgs = []

    for row in reader:
        if args.address is None or int(args.address) == int(row[address_col]):
            msgs.append(
                {
                    "body": row[msg_body_col],
                    "time_sent":
                        time.ctime(int(row[time_received_col]) / 1000.0),
                    "time_sent_int": int(row[time_received_col])
                }
            )
    get_media(args, msgs)
    return sort_msgs(msgs)


def load_mms_data(args):
    time_received_col = 2
    msg_body_col = 10
    address_col = 14

    msgs = []

    reader = \
        csv.reader(open(args.mms_backup_file, newline=""),
                   skipinitialspace=True)
    next(reader, None)
    for row in reader:
        if args.address is None or int(args.address) == int(row[address_col]):
            msgs.append(
                {
                    "body": row[msg_body_col],
                    "time_sent":
                        time.ctime(int(row[time_received_col]) / 1000.0),
                    "time_sent_int": int(row[time_received_col])
                }
            )

    get_media(args, msgs)
    return sort_msgs(msgs)


def load_emails(args):
    email_dir = Path(args.email_directory)
    report_dir = Path(args.output_directory)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
              "Aug", "Sep", "Oct", "Nov", "Dec"]
    if not email_dir.exists() or not email_dir.is_dir():
        raise Exception("Email path {args.email_directory} does not exist")
    report_dir.mkdir(exist_ok=True)
    msgs = []
    for file_ in email_dir.iterdir():
        if file_.suffix == ".eml":
            eml = Parser().parse(file_.open(), headersonly=False)
            date_split = eml["Date"].split()
            day = int(date_split[1])
            month = months.index(date_split[2]) + 1
            year = int(date_split[3])
            time_split = date_split[4].split(":")
            hr = int(time_split[0])
            minute = int(time_split[1])
            sec = int(time_split[2])

            msg = {
                "time_sent_int":
                    str(int(datetime.datetime(
                        year, month, day, hr, minute, sec).timestamp())),
                "time_sent": eml["Date"],
                "subject": eml["Subject"],
                "from": eml["From"],
                "to": eml["To"],
                "reply-to": eml["Reply-To"],
                "body": ""
            }
            msg_dir = report_dir / str(msg["time_sent_int"])

            if eml.is_multipart():
                # iterate over email parts
                for part in eml.walk():
                    # extract content type of email
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    try:
                        # get the email body
                        body = part.get_payload(decode=True).decode()
                    except Exception:
                        pass
                    if content_type == "text/plain" and \
                            "attachment" not in content_disposition:
                        # print text/plain emails and skip attachments
                        msg["body"] = body
                    elif "attachment" in content_disposition:
                        filename = part.get_filename()
                        print(filename)
                        if filename:
                            msg_dir.mkdir(exist_ok=True)
                            filepath = msg_dir / filename
                            if "attachments" not in body:
                                msg["attachments"] = []
                            msg["attachments"].append(
                                str(msg["time_sent_int"]) + "/" + filename)
                            filepath.write_bytes(part.get_payload(decode=True))
            else:
                content_type = eml.get_content_type()
                body = eml.get_payload(decode=True).decode()
                if content_type == "text/plain":
                    msg["body"] = body

            if content_type == "text/html":
                msg_dir.mkdir(exist_ok=True)
                filepath = msg_dir / "index.html"
                filepath.write_text(body)
                if "attachments" not in msg:
                    msg["attachments"] = []
                msg["attachments"].append(str(msg["time_sent_int"]) +
                                          "/index.html")

            msgs.append(msg)

    return sort_msgs(msgs)


def repl_obscenity(m):
    return '<span style="background-color: #FFFF00">' + m.group(0) + '</span>'


def obscenity_check(
        msgs, obscenities=[
            'fuck', 'shit', 'cock', r'\b(ass)\b', 'dick', 'cunt', 'dildo',
            'douche', 'fag', 'fudgepacker', 'gay', 'nazi', 'pecker', 'penis',
            'pussy', 'poon', 'queer', 'schlong', 'retard', 'twat', 'ugly',
            'vagina', 'whore', 'masturbat', 'bitch', 'asshole', 'prick',
            'creep', 'crap', r'\b(fool)\b', 'dousch', 'slut', 'stupid']):
    count = 0
    expr = [re.compile(obscenity, re.IGNORECASE) for obscenity in obscenities]
    for msg in msgs:
        obscenity_count = 0
        msg_body = msg["body"]
        for ex in expr:
            if not("fool" in msg_body and "http" in msg_body):
                (msg_body, n) = ex.subn(repl_obscenity, msg_body)
            obscenity_count += n
        msg["body_highlight"] = msg_body.replace("*", r"\*")
        msg["obscenity_found"] = (obscenity_count > 0)
        if obscenity_count > 0:
            count += 1
    return count / len(msgs) * 100.0


def repl_url(m):
    return '<' + m.group(0) + '>'


def clean_urls(msgs):
    ex = re.compile(r".*(http[s]?://.*)[\w$]")
    for msg in msgs:
        msg["body"] = ex.sub(repl_url, msg["body"])


def generate_month_range(start, stop):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
              "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_range = []
    i = months.index(start[0])
    while True:
        y, m = divmod(i, 12)
        year = start[1] + y
        if months[m] == stop[0] and year == stop[1]:
            break
        month_range.append((months[m], year))
        i += 1
    return month_range


def plot_freq_month(msgs, emails, start=("Mar", 2020), stop=("Apr", 2021)):
    months = generate_month_range(start, stop)

    plt.clf()
    plt.figure(figsize=(12, 8))
    msg_month_bins = [0 for i in range(len(months))]
    for msg in msgs:
        date_parsed = msg["time_sent"].replace(':', ' ').split(' ')
        for i, (month, year) in enumerate(months):
            if date_parsed[1] == month and int(date_parsed[6]) == year:
                msg_month_bins[i] += 1
    plt.plot(range(len(months)), msg_month_bins, label="text messages")

    email_month_bins = [0 for i in range(len(months))]
    for email in emails:
        date_parsed = email["time_sent"].replace(':', ' ').split(' ')
        for i, (month, year) in enumerate(months):
            if date_parsed[2] == month and int(date_parsed[3]) == year:
                email_month_bins[i] += 1
    plt.plot(range(len(months)), email_month_bins, label="emails")

    ax = plt.gca()
    ax.grid(which='major', axis='y', linestyle='--')
    labels = [f"{i[0]} {i[1]}" for i in months]
    plt.xticks(range(len(months)), labels=labels, rotation='vertical')
    plt.ylabel("Frequency")
    plt.title("Messages received by month")
    plt.subplots_adjust(bottom=0.30)
    plt.legend()

    output_dir = Path(args.output_directory)
    output_dir.mkdir(exist_ok=True)
    plt.savefig(output_dir / "month_frequency.png")


def plot_freq_week(msgs, emails):
    msg_day_bins = [0 for i in range(7)]
    email_day_bins = [0 for i in range(7)]
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for msg in msgs:
        date_parsed = msg["time_sent"].replace(':', ' ').split(' ')
        for i, day in enumerate(days):
            if date_parsed[0] == day:
                msg_day_bins[i] += 1
    for email in emails:
        date_parsed = email["time_sent"].replace(':', ' ').split(' ')
        for i, day in enumerate(days):
            if date_parsed[0].strip(",") == day:
                email_day_bins[i] += 1
    plt.clf()
    plt.figure(figsize=(12, 8))
    plt.plot(range(7), msg_day_bins, label="text messages")
    plt.plot(range(7), email_day_bins, label="emails")
    plt.legend()
    ax = plt.gca()
    ax.grid(which='major', axis='y', linestyle='--')
    plt.xticks(range(7), labels=days, rotation='vertical')
    plt.xlabel("Day")
    plt.ylabel("Frequency")
    plt.title("Messages received by day of week")
    plt.subplots_adjust(bottom=0.15)
    output_dir = Path(args.output_directory)
    output_dir.mkdir(exist_ok=True)
    plt.savefig(output_dir / "week_frequency.png")


def plot_freq_day(msgs, emails):
    msg_hr_bins = [0 for i in range(24)]
    email_hr_bins = [0 for i in range(24)]
    for msg in msgs:
        hr = int(msg["time_sent"].replace(':', ' ').split(' ')[3])
        msg_hr_bins[hr] += 1
    for email in emails:
        hr = int(email["time_sent"].replace(':', ' ').split(' ')[4])
        email_hr_bins[hr] += 1

    plt.clf()
    plt.figure(figsize=(12, 8))
    plt.plot(range(24), msg_hr_bins, label="text messages")
    plt.plot(range(24), email_hr_bins, label="emails")
    ax = plt.gca()
    ax.grid(which='major', axis='y', linestyle='--')
    plt.xticks(range(24), rotation='vertical')
    plt.xlabel("Time of day")
    plt.ylabel("Frequency")
    plt.title("Messages received by time of day")
    plt.legend()
    plt.subplots_adjust(bottom=0.15)
    output_dir = Path(args.output_directory)
    output_dir.mkdir(exist_ok=True)
    plt.savefig(output_dir / "day_frequency.png")


def write_report(args, msgs, emails, msgs_obscenity_pct=None,
                 emails_obscenity_pct=None):
    output_dir = Path(args.output_directory)
    output_dir.mkdir(exist_ok=True)
    report_md = output_dir / args.output_file
    report_pdf = output_dir / "report.pdf"

    print(f"Generating report {report_md}...")

    with report_md.open("w") as f:
        f.write("# Text messages and emails ")
        if args.name is not None:
            f.write(f"from {args.name} ")
        if args.date is not None:
            f.write(f"received since {args.date}")
        f.write("\n\n")
        # f.write("## Contents\n\n")
        # f.write("  * [Text messages](#text-messages)\n")
        # f.write("  * [Emails](#emails)\n")
        # f.write("\n\n")

        f.write("## Summary\n\n")

        f.write("### Overview\n\n")

        f.write(f"  * Processed {len(msgs)} text messages\n")
        if msgs_obscenity_pct is not None:
            f.write(f"  * **{format(msgs_obscenity_pct, '0.2f')}% of "
                    "text messages flagged for aggressive content based on "
                    "key word search.**\n\n")

        f.write(f"  * Processed {len(emails)} emails\n")
        if emails_obscenity_pct is not None:
            f.write(f"  * **{format(emails_obscenity_pct, '0.2f')}% of emails "
                    "flagged for aggressive content based on key word "
                    "search.**\n\n")

        f.write("### Messages received by month\n\n")
        f.write("![messages received by month](month_frequency.png)\n\n")

        f.write("### Messages received by day of week\n\n")
        f.write("![messages received by month](week_frequency.png)\n\n")

        f.write("### Messages received by time of day\n\n")
        f.write("![messages received by month](day_frequency.png)\n\n")

        f.write("## Text messages\n\n")
        if msgs_obscenity_pct is not None:
            f.write(f"**{format(msgs_obscenity_pct, '0.2f')}% of text "
                    "messages flagged for aggressive content based on key "
                    "word search.** See highlighted key words in report\n\n")

        # detect youtube video links
        ex = re.compile(r".*<http[s]?://.*youtube.*?=(.*?)>")
        for msg in msgs:
            f.write(f"### {msg['time_sent']}\n\n")
            f.write(f"{msg['body_highlight']}\n\n")
            if "http" in msg["body"] and "youtube" in msg["body"]:
                m = ex.match(msg['body'])
                # display youtube video previews
                if m:
                    f.write(
                        f"![{m.group(0).strip('<>')}]"
                        f"(https://img.youtube.com/vi/{m.group(1)}/0.jpg)\n\n")

            for media in msg.get('media', []):
                f.write(f"![{media}](./{media})\n")
            f.write("\n")
        f.write("\n\n")

        f.write("## Emails\n\n")
        if emails_obscenity_pct is not None:
            f.write(
                f"**{format(emails_obscenity_pct, '0.2f')}% of emails "
                "flagged for aggressive content based on key word search.** "
                "See highlighted key words in report\n\n")

        ex = re.compile(r".*<https?://.*youtube.*?=(.*?)>")
        for email in emails:
            f.write(f"### {email['time_sent']}\n\n")

            f.write(f"**Subject:** {email['subject']}<br>")
            f.write(f"**From:** {email['from']}<br>")
            f.write(f"**To:** {email['to']}<br>")
            f.write(f"**Reply-to:** {email['reply-to']}\n\n")

            f.write(f"{email['body_highlight']}\n\n")
            if "http" in email["body"] and "youtube" in email["body"]:
                m = ex.match(email['body'])
                # display youtube video previews
                if m:
                    f.write(
                        f"![{m.group(0).strip('<>')}]"
                        f"(https://img.youtube.com/vi/{m.group(1)}/0.jpg)\n\n")

            for media in email.get('attachments', []):
                if Path(media).suffix == ".html":
                    ex2 = re.compile(r".*\"https?://.*youtube.*?=(.*?)\"")
                    match = []
                    with (Path(args.output_directory) / media).open("r") as g:
                        for line in g:
                            m = ex2.match(line)
                            if m:
                                match.append(m)
                            f.write(f"{line}\n")
                    for m in match:
                        f.write("\n\n")
                        txt = f"https://img.youtube.com/vi/{m.group(1)}/0.jpg"
                        f.write(f"![{txt}]({txt})\n\n")
                else:
                    f.write(f"![{media}](./{media})\n\n")
            f.write("\n")

    print(f"Generating report {report_pdf}...")
    result = subprocess.run(["md2pdf", str(report_md), "-o", str(report_pdf)],
                            env={"QTWEBKIT_IMAGEFORMAT_WHITELIST": "pdf"},
                            capture_output=True,
                            check=False)
    print(result.stderr.decode())
    print(result.stdout.decode())


if __name__ == "__main__":
    args = parse_args()

    sms_msgs = load_sms_data(args)
    mms_msgs = load_mms_data(args)
    msgs = sort_msgs(sms_msgs + mms_msgs)

    clean_urls(msgs)

    emails = load_emails(args)

    plot_freq_week(msgs, emails)
    plot_freq_day(msgs, emails)
    plot_freq_month(msgs, emails)

    msgs_obscenity_pct = obscenity_check(msgs)
    emails_obscenity_pct = obscenity_check(emails)

    write_report(args, msgs, emails,
                 msgs_obscenity_pct=msgs_obscenity_pct,
                 emails_obscenity_pct=emails_obscenity_pct)
