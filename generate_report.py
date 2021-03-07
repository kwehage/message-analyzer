#!/usr/bin/env python

import csv
import time
import math
import matplotlib.pyplot as plt
import argparse
from pathlib import Path
from operator import itemgetter
from email.parser import Parser
from email.header import decode_header
import re
import datetime
import subprocess


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
    tol = 7000  # milliseconds
    if not media_dir.exists() or not media_dir.is_dir():
        raise Exception("Media path {args.media_directory} does not exist")
    for file_ in media_dir.iterdir():
        timestamp = file_.stem
        for msg in msgs:
            if math.fabs(msg["time_sent_int"] - int(timestamp)) < tol:
                if "media" not in msg:
                    msg["media"] = []
                msg["media"].append(str(file_))
    for msg in msgs:
        if "media" in msg:
            print(msg["media"])
        else:
            print(f"No media for msg {msg['time_sent_int']}")


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
            # print("Subject: ", eml["Subject"])
            # print("Date: ", eml["Date"])

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
                        if filename:
                            msg_dir.mkdir(exist_ok=True)
                            filepath = msg_dir / filename
                            if "attachments" not in body:
                                msg["attachments"] = []
                            msg["attachments"].append(str(filepath))
                            print(filepath)
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
                msg["attachments"].append(str(filepath))

            msgs.append(msg)

    return sort_msgs(msgs)


def repl(m):
    return '<span style="background-color: #FFFF00">' + m.group(0) + '</span>'


def obscenity_check(
        msgs, obscenities=[
            'fuck', 'shit', 'cock', r'\b(ass)\b', 'dick', 'cunt', 'dildo',
            'douche', 'fag', 'fudgepacker', 'gay', 'nazi', 'pecker', 'penis',
            'pussy', 'poon', 'queer', 'schlong', 'retard', 'twat', 'ugly',
            'vagina', 'whore', 'masturbat', 'bitch', 'asshole', 'prick',
            'creep', 'crap', 'fool']):
    count = 0
    expr = [re.compile(obscenity, re.IGNORECASE) for obscenity in obscenities]
    for msg in msgs:
        obscenity_count = 0
        msg_body = msg["body"]
        for ex in expr:
            (msg_body, n) = ex.subn(repl, msg_body)
            obscenity_count += n
        msg["body_highlight"] = msg_body.replace("*", "\*")
        msg["obscenity_found"] = (obscenity_count > 0)
        if obscenity_count > 0:
            count += 1
    print("obscenities found in {:0.2f}% of messages".format(
        count / len(msgs) * 100.0))


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


def plot_freq_month(msgs, start=("Mar", 2020), stop=("Apr", 2021)):
    months = generate_month_range(start, stop)
    month_bins = [0 for i in range(len(months))]
    for msg in msgs:
        date_parsed = msg["time_sent"].replace(':', ' ').split(' ')
        for i, (month, year) in enumerate(months):
            if date_parsed[1] == month and int(date_parsed[6]) == year:
                month_bins[i] += 1
    plt.clf()
    plt.plot(range(len(months)), month_bins)
    labels = [f"{i[0]} {i[1]}" for i in months]
    plt.xticks(range(len(months)), labels=labels, rotation='vertical')
    plt.ylabel("Frequency")
    plt.title("Messages received per month")
    plt.subplots_adjust(bottom=0.30)
    output_dir = Path(args.output_directory)
    output_dir.mkdir(exist_ok=True)
    plt.savefig(output_dir / "month_frequency.png")


def plot_freq_week(msgs):
    day_bins = [0 for i in range(7)]
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for msg in msgs:
        date_parsed = msg["time_sent"].replace(':', ' ').split(' ')
        for i, day in enumerate(days):
            if date_parsed[0] == day:
                day_bins[i] += 1
    plt.clf()
    plt.plot(range(7), day_bins)
    plt.xticks(range(7), labels=days, rotation='vertical')
    plt.xlabel("Day")
    plt.ylabel("Frequency")
    plt.title("Messages received per day of week")
    plt.subplots_adjust(bottom=0.15)
    output_dir = Path(args.output_directory)
    output_dir.mkdir(exist_ok=True)
    plt.savefig(output_dir / "week_frequency.png")


def plot_freq_day(msgs):
    hr_bins = [0 for i in range(24)]
    for msg in msgs:
        hr = int(msg["time_sent"].replace(':', ' ').split(' ')[3])
        hr_bins[hr] += 1
    plt.clf()
    plt.plot(range(24), hr_bins)
    plt.xticks(range(24), rotation='vertical')
    plt.xlabel("Time of day")
    plt.ylabel("Frequency")
    plt.title("Messages received per time of day")
    plt.subplots_adjust(bottom=0.15)
    output_dir = Path(args.output_directory)
    output_dir.mkdir(exist_ok=True)
    plt.savefig(output_dir / "day_frequency.png")


def write_report(args, msgs, emails):
    output_dir = Path(args.output_directory)
    output_dir.mkdir(exist_ok=True)
    report_md = output_dir / args.output_file
    report_pdf = output_dir / "report.pdf"

    print(f"Generating report: {report_md}")

    with report_md.open("w") as f:
        f.write("# SMS Messages received ")
        if args.name is not None:
            f.write(f"from {args.name} ")
        if args.date is not None:
            f.write(f"since {args.date}")
        f.write("\n")

        for msg in msgs:
            f.write(f"## {msg['time_sent']}\n\n")
            f.write(f"{msg['body_highlight']}\n")
            for media in msg.get('media', []):
                f.write(f"{media}\n")
            f.write("\n")

    subprocess.run(["md2pdf", str(report_md), "-o", str(report_pdf)])


if __name__ == "__main__":
    args = parse_args()

    sms_msgs = load_sms_data(args)
    mms_msgs = load_mms_data(args)
    msgs = sort_msgs(sms_msgs + mms_msgs)

    emails = load_emails(args)

    plot_freq_week(msgs)
    plot_freq_day(msgs)
    plot_freq_month(msgs)

    obscenity_check(msgs)
    obscenity_check(emails)

    write_report(args, msgs, emails)

