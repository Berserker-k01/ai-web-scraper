from typing import List

from pydantic import BaseModel, Field


class ListingItem(BaseModel):
    profile_url: str = Field(..., description="Full URL to the company profile/detail page.")
    company_name: str = Field(default="", description="Company name if visible in the listing.")


class ListingPageResult(BaseModel):
    companies: List[ListingItem] = Field(
        default_factory=list,
        description="Business listings found on the page (exclude ads and navigation).",
    )
    next_page_url: str = Field(
        default="",
        description="Absolute URL of the next results page. Empty if this is the last page.",
    )


class ContactEnrichment(BaseModel):
    phone: str = Field(default="", description="Primary phone number.")
    secondary_phones: List[str] = Field(default_factory=list)
    email: str = Field(default="", description="Primary email address.")
    emails: List[str] = Field(default_factory=list)
    facebook: str = Field(default="")
    linkedin: str = Field(default="")
    instagram: str = Field(default="")
    whatsapp: str = Field(default="")


class BusinessLead(BaseModel):
    company_name: str = Field(..., description="Official company name.")
    industry: str = Field(default="", description="Business sector or industry.")
    description: str = Field(default="", description="Company description.")
    address: str = Field(default="", description="Full street address.")
    city: str = Field(default="", description="City.")
    country: str = Field(default="", description="Country.")
    phone: str = Field(default="", description="Primary phone number.")
    secondary_phones: List[str] = Field(default_factory=list, description="Additional phone numbers.")
    email: str = Field(default="", description="Primary email address.")
    emails: List[str] = Field(default_factory=list, description="Additional email addresses.")
    website: str = Field(default="", description="Company website URL.")
    facebook: str = Field(default="", description="Facebook profile or page URL.")
    linkedin: str = Field(default="", description="LinkedIn company or profile URL.")
    instagram: str = Field(default="", description="Instagram profile URL.")
    whatsapp: str = Field(default="", description="WhatsApp contact link or number.")
    latitude: str = Field(default="", description="GPS latitude if available.")
    longitude: str = Field(default="", description="GPS longitude if available.")
    source_url: str = Field(default="", description="Source profile URL where data was found.")

    def to_export_row(self) -> dict:
        phones = [self.phone] if self.phone else []
        phones.extend(p for p in self.secondary_phones if p and p not in phones)

        emails = [self.email] if self.email else []
        emails.extend(e for e in self.emails if e and e not in emails)

        return {
            "Company Name": self.company_name,
            "Industry": self.industry,
            "Description": self.description,
            "Address": self.address,
            "City": self.city,
            "Country": self.country,
            "Phone": "; ".join(phones),
            "Email": "; ".join(emails),
            "Website": self.website,
            "Facebook": self.facebook,
            "LinkedIn": self.linkedin,
            "Instagram": self.instagram,
            "WhatsApp": self.whatsapp,
            "Latitude": self.latitude,
            "Longitude": self.longitude,
            "Source URL": self.source_url,
        }
