# Small helper functions shared by the monitoring scripts.

import csv
import platform
import smtplib
import subprocess
from datetime import datetime
from email.message import EmailMessage

import paramiko

import config


def now():
    # The current date and time, e.g. "2026-10-30 20:15:00"
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_devices():
    # Read network_devices.csv and return a list of rows (dictionaries)
    devices = []
    with open(config.CSV_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            devices.append(row)
    return devices


def ping(ip):
    # Ping an IP address once. Returns True if it answered.
    if platform.system() == "Windows":
        command = ["ping", "-n", "1", "-w", "1000", ip]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode == 0


def run_ssh(ip, username, password, command):
    # Log in to a device over SSH, run one command, and return its output.
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=username, password=password, timeout=10)
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode()
    client.close()
    return output


def send_email(subject, body):
    # Send an email through the lab's SMTP server
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.EMAIL_FROM
    message["To"] = config.EMAIL_TO
    message.set_content(body)
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.send_message(message)
    print("    Email sent: " + subject)
