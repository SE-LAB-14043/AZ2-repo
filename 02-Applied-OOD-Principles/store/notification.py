from store.protocols import EmailSender, SmsSender, PushSender


class ConsoleEmailSender:
    def send_email(self, customer, message: str) -> None:
        print(f"[email] to {customer.email}: {message}")


class ConsoleSmsSender:
    def send_sms(self, customer, message: str) -> None:
        print(f"[sms] to {customer.phone}: {message}")


class ConsolePushSender:
    def send_push(self, customer, message: str) -> None:
        print(f"[push] to {customer.name}: {message}")
