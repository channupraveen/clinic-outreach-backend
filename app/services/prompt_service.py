from app.models.clinic_model import Clinic


ISSUE_DESCRIPTIONS = {
    "no_booking": "The clinic has no online booking system — patients can only book by phone, which creates friction and lost leads, especially for younger demographics.",
    "outdated_website": "The clinic's website looks outdated (old design, not mobile-friendly, poor typography) which hurts credibility and first impressions with prospective patients.",
    "no_chatbot": "There's no chatbot or auto-reply on the website, so leads who visit after-hours or have quick questions get no response and often go to a competitor.",
    "slow_website": "The website loads slowly, which increases bounce rate and hurts Google rankings — directly impacting new patient acquisition.",
    "no_seo": "The clinic has weak local SEO — it doesn't show up on the first page for key local searches like '[specialty] near me' in their city.",
}

SERVICE_DESCRIPTIONS = {
    "website_redesign": "A modern, mobile-first website redesign with fast load times and a clean, trust-building aesthetic",
    "booking_system": "An integrated online booking system that syncs with their existing calendar",
    "ai_chatbot": "An AI-powered chatbot that handles FAQs, captures leads 24/7, and books appointments automatically",
    "seo": "A local SEO optimization package targeting their top 10 service keywords in their city",
    "full_package": "A complete digital overhaul — new website, booking system, AI chatbot, and local SEO",
}


def generate_prompt(clinic: Clinic, issue: str, service: str, tone: str = "friendly") -> str:
    """Generate a Claude-ready prompt to write a personalized cold email."""
    issue_desc = ISSUE_DESCRIPTIONS.get(issue, issue)
    service_desc = SERVICE_DESCRIPTIONS.get(service, service)

    prompt = f"""You are writing a personalized cold email for a B2B outreach campaign targeting US medical clinics.

CLINIC DETAILS
Clinic Name: {clinic.clinic_name}
Clinic Type: {clinic.clinic_type or 'Medical clinic'}
Location: {clinic.city or 'N/A'}, {clinic.state or 'N/A'}, USA
Website: {clinic.website or 'N/A'}

OBSERVATION (specific pain point we noticed)
{issue_desc}

SERVICE WE OFFER
{service_desc}

INSTRUCTIONS
Write a short, personalized cold email (strictly under 130 words) that:
- Opens with a specific, genuine observation about their clinic (not generic flattery)
- Clearly connects the observation to the value we can deliver
- Mentions one concrete outcome they can expect
- Ends with a soft, low-pressure call-to-action (e.g. "Would you be open to a 10-minute call?")
- Sounds human, warm, and {tone} — NOT salesy, robotic, or templated
- Does NOT use phrases like "I hope this email finds you well", "I wanted to reach out", or "synergy"
- Uses the clinic name naturally (not awkwardly stuffed in)

FORMAT
Return the response as:

Subject: <a short, curiosity-driven subject line under 8 words>

<body of the email>

— [Your Name]
DevSpark Studio
"""
    return prompt
