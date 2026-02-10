"""Email sender for house listing notifications."""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any


class EmailSender:
    """Send listing notifications via Gmail SMTP."""

    def __init__(
        self,
        gmail_address: str | None = None,
        gmail_app_password: str | None = None,
    ):
        self.gmail_address = gmail_address or os.environ.get("GMAIL_ADDRESS")
        self.gmail_app_password = gmail_app_password or os.environ.get(
            "GMAIL_APP_PASSWORD"
        )

        if not self.gmail_address or not self.gmail_app_password:
            raise ValueError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD are required")

    def send_listings(
        self,
        recipient: str,
        listings: list[dict[str, Any]],
        subject_prefix: str = "Austin Houses",
    ) -> bool:
        """
        Send an email with house listings.

        Args:
            recipient: Email address to send to
            listings: List of listing dictionaries
            subject_prefix: Prefix for email subject

        Returns:
            True if email sent successfully
        """
        if not listings:
            return self._send_no_listings_email(recipient, subject_prefix)

        date_str = datetime.now().strftime("%b %d")
        subject = f"{subject_prefix} - {len(listings)} New Matches ({date_str})"

        html_content = self._build_html(listings)
        text_content = self._build_text(listings)

        return self._send_email(recipient, subject, html_content, text_content)

    def _send_no_listings_email(self, recipient: str, subject_prefix: str) -> bool:
        """Send an email when no listings match."""
        date_str = datetime.now().strftime("%b %d")
        subject = f"{subject_prefix} - No New Matches ({date_str})"

        html_content = """
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>No New Listings Found</h2>
            <p>No properties matched your criteria this time. We'll check again soon!</p>
        </body>
        </html>
        """
        text_content = "No new listings matched your criteria this time."

        return self._send_email(recipient, subject, html_content, text_content)

    def _build_html(self, listings: list[dict[str, Any]]) -> str:
        """Build HTML email content."""
        listing_cards = ""

        for listing in listings:
            price = listing.get("price", 0)
            price_str = f"${price:,}" if price else "Price N/A"

            address = listing.get("address", "Address N/A")
            city = listing.get("city", "")
            state = listing.get("state", "")
            location = f"{city}, {state}" if city and state else ""

            beds = listing.get("beds", "?")
            baths = listing.get("baths", "?")
            sqft = listing.get("sqft")
            sqft_str = f"{sqft:,} sqft" if sqft else ""

            days = listing.get("days_on_market", 0)
            days_str = f"Listed {days} days ago" if days else "New listing"

            photo_url = listing.get("photo_url", "")
            zillow_url = listing.get("zillow_url", "")

            photo_html = ""
            if photo_url:
                photo_html = f'<img src="{photo_url}" alt="Property" style="width: 100%; max-height: 200px; object-fit: cover; border-radius: 8px 8px 0 0;">'

            listing_cards += f"""
            <div style="border: 1px solid #ddd; border-radius: 8px; margin-bottom: 20px; overflow: hidden; max-width: 400px;">
                {photo_html}
                <div style="padding: 15px;">
                    <div style="font-size: 24px; font-weight: bold; color: #1a73e8;">{price_str}</div>
                    <div style="font-size: 16px; margin-top: 5px;">{address}</div>
                    <div style="color: #666; font-size: 14px;">{location}</div>
                    <div style="margin-top: 10px; font-size: 14px;">
                        <strong>{beds}</strong> bed | <strong>{baths}</strong> bath {f'| <strong>{sqft_str}</strong>' if sqft_str else ''}
                    </div>
                    <div style="color: #888; font-size: 12px; margin-top: 5px;">{days_str}</div>
                    <a href="{zillow_url}" style="display: inline-block; margin-top: 15px; padding: 10px 20px; background-color: #1a73e8; color: white; text-decoration: none; border-radius: 5px;">View on Zillow</a>
                </div>
            </div>
            """

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Found {len(listings)} properties matching your criteria</h2>
                {listing_cards}
                <p style="color: #888; font-size: 12px; margin-top: 30px;">
                    This email was sent by Austin House Hunter.
                    <a href="https://github.com/yourusername/austin-house-hunter">View on GitHub</a>
                </p>
            </div>
        </body>
        </html>
        """

    def _build_text(self, listings: list[dict[str, Any]]) -> str:
        """Build plain text email content."""
        lines = [f"Found {len(listings)} properties matching your criteria:\n"]

        for listing in listings:
            price = listing.get("price", 0)
            price_str = f"${price:,}" if price else "Price N/A"

            address = listing.get("address", "Address N/A")
            beds = listing.get("beds", "?")
            baths = listing.get("baths", "?")
            sqft = listing.get("sqft")
            sqft_str = f" | {sqft:,} sqft" if sqft else ""
            zillow_url = listing.get("zillow_url", "")

            lines.append(f"{price_str} - {address}")
            lines.append(f"{beds} bed | {baths} bath{sqft_str}")
            if zillow_url:
                lines.append(f"View: {zillow_url}")
            lines.append("")

        return "\n".join(lines)

    def _send_email(
        self,
        recipient: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        """Send the email via Gmail SMTP."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.gmail_address
        msg["To"] = recipient

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.gmail_address, self.gmail_app_password)
                server.sendmail(self.gmail_address, recipient, msg.as_string())
            print(f"Email sent successfully to {recipient}")
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
