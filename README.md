# Generate report of emails and text messages
Generate a summary report of emails and text messages using protonmail 
encrypted email service and Signal messenger

## Backing up Signal messages
To backup data from signal, go to `Settings` -> `Chats` -> `Chat Backups` -> `Turn On`
Make note of the 30 digit encryption key

Download signal-back executable for your platform from 
https://github.com/xeals/signal-back or follow instructions to build from
source (requires go).

Connect your phone to your computer and copy the backup file to your computer.
On my phone the backup was located in the `Signal` folder and the backup
file was called `signal-2021-03-06-11-06-10.backup`

Extract media embedded in backup; replace the X's with your 30 digit
encryption key:
```
./signal-back_linux_amd64 extract -p <XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX> --verbose -o images
```

Extract sms messages (limited to 160 characters) to CSV format:
```
./signal-back_linux_amd64 format -p <XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX> --verbose -M sms -o sms.csv
```

Extract mms messages (no limit on characters) to CSV format
```
./signal-back_linux_amd64 format -p <XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX> --verbose -M mms -o mms.csv
```

## Backing up protonmail messages
Install the protonmail bridge for your operating system, available to download from https://protonmail.com/bridge/install

On arch linux it is available through third party repositories, it can be installed using a package manager such as `yay` as:
```
yay -S protonmail-bridge 
```

Launch the application, and enter your protonmail credentials to connect your account.

Configure your email client by following instructions at https://protonmail.com/bridge/clients

After downloading the messages in your email client, select the messages you want to parse and save to
your hard drive in `.eml` format. In this example, we will save all emails to the folder `emails`.


## Generate PDF Report and plots
Use `generate_report.py` to create summary document of your messages:
```bash
python generate_report.py -S sms.csv -M mms.csv -E emails -I images \
    -N "John Doe" -A 14 -O "report" -F report.md
```
Here `-A` corresponds to the numeric address of the person you want to
print messages for. Open the CSV file to find the address. If you do not 
specify the address, it will print all messages.

A complete list of options can be found by running 
`python generate_report.py --help`:
```bash
Generate a PDF report and plots from a decrypted signal backup and email messages

optional arguments:
  -h, --help            show this help message and exit
  --sms-backup-file SMS_BACKUP_FILE, -S SMS_BACKUP_FILE
                        Signal backup file in sms/csv format
  --address ADDRESS, -A ADDRESS
                        Numeric ID for sms message
  --mms-backup-file MMS_BACKUP_FILE, -M MMS_BACKUP_FILE
                        Signal backup file in sms/csv format
  --email-directory EMAIL_DIRECTORY, -E EMAIL_DIRECTORY
                        Folder containing email messages
  --media-directory MEDIA_DIRECTORY, -I MEDIA_DIRECTORY
                        Folder containing media files
  --name NAME, -N NAME  Name of person to use in report
  --output-directory OUTPUT_DIRECTORY, -O OUTPUT_DIRECTORY
                        Directory to store output plots and summary report
  --date DATE, -D DATE  Show only messages after date
  --output-file OUTPUT_FILE, -F OUTPUT_FILE
                        Report filename
```
