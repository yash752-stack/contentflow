"""
api/routes/ai_assistant.py
AI content assistant — the feature most relevant to Publive's AI-powered CMS.
Provides: SEO suggestions, auto-excerpt, tag recommendations, readability scoring,
headline variants, and content improvement suggestions.
Uses rule-based NLP (no API key needed to demo) with Groq/LLM integration path shown.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import re
import math
from collections import Counter

router = APIRouter()


# ── SCHEMAS ────────────────────────────────────────────────────────────────

class ContentAnalysisRequest(BaseModel):
    title:   str = Field(..., min_length=3)
    content: str = Field(..., min_length=50)
    target_keyword: Optional[str] = None

class HeadlineRequest(BaseModel):
    topic:   str = Field(..., min_length=5)
    style:   str = Field("news", description="news | listicle | how-to | question")

class TagSuggestionRequest(BaseModel):
    title:   str
    content: str
    max_tags: int = Field(5, ge=1, le=10)


# ── NLP UTILITIES ──────────────────────────────────────────────────────────

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "this", "that", "these", "those", "i", "we",
    "you", "he", "she", "it", "they", "their", "its", "our", "your",
    "which", "who", "what", "how", "when", "where", "why", "as", "if",
    "not", "no", "so", "also", "more", "than", "then", "now", "can",
}

POWER_WORDS = [
    "ultimate", "essential", "proven", "complete", "powerful", "effective",
    "simple", "fast", "easy", "best", "top", "new", "free", "exclusive",
    "secret", "surprising", "amazing", "important", "critical", "key",
]


def count_sentences(text: str) -> int:
    return len(re.findall(r"[.!?]+", text)) or 1


def count_words(text: str) -> int:
    return len(text.split())


def flesch_reading_ease(text: str) -> float:
    """Flesch Reading Ease score: higher = easier to read."""
    words = count_words(text)
    sentences = count_sentences(text)
    syllables = sum(count_syllables(w) for w in text.split())
    if words == 0 or sentences == 0:
        return 0.0
    score = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    return round(max(0, min(100, score)), 1)


def count_syllables(word: str) -> int:
    word = word.lower().strip(".,!?;:")
    count = len(re.findall(r"[aeiou]", word))
    count -= len(re.findall(r"[aeiou]{2}", word))
    return max(1, count)


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    filtered = [w for w in words if w not in STOP_WORDS]
    freq = Counter(filtered)
    return [word for word, _ in freq.most_common(top_n)]


def keyword_density(text: str, keyword: str) -> float:
    words = text.lower().split()
    count = words.count(keyword.lower())
    return round((count / len(words)) * 100, 2) if words else 0.0


def seo_score(title: str, content: str, keyword: Optional[str]) -> dict:
    score = 0
    issues = []
    suggestions = []

    # Title length (50-60 chars is ideal)
    title_len = len(title)
    if 50 <= title_len <= 60:
        score += 20
    elif title_len < 50:
        score += 10
        suggestions.append(f"Title is {title_len} chars — aim for 50–60 for best SEO.")
    else:
        score += 5
        suggestions.append(f"Title is {title_len} chars — over 60 may get truncated in search results.")

    # Content length
    word_count = count_words(content)
    if word_count >= 1500:
        score += 20
    elif word_count >= 800:
        score += 15
        suggestions.append(f"Content is {word_count} words. Aim for 1500+ for long-form SEO.")
    else:
        score += 5
        issues.append(f"Content is only {word_count} words — too short for competitive SEO.")

    # Keyword usage
    if keyword:
        density = keyword_density(content, keyword)
        in_title = keyword.lower() in title.lower()
        if in_title:
            score += 20
        else:
            issues.append(f"Target keyword '{keyword}' not found in title.")
        if 0.5 <= density <= 2.5:
            score += 20
        elif density > 2.5:
            issues.append(f"Keyword density {density}% is too high — looks like keyword stuffing.")
        else:
            suggestions.append(f"Keyword density is {density}% — aim for 1–2%.")
    else:
        score += 20

    # Headings check (H2, H3 presence)
    has_headings = bool(re.search(r"#{2,3}\s", content)) or bool(re.search(r"<h[23]", content))
    if has_headings:
        score += 10
    else:
        suggestions.append("Add H2/H3 subheadings to improve readability and SEO structure.")

    # Power words in title
    has_power = any(pw in title.lower() for pw in POWER_WORDS)
    if has_power:
        score += 10
    else:
        suggestions.append("Consider adding a power word to the title (e.g. 'Complete', 'Essential', 'Proven').")

    return {
        "score":       min(100, score),
        "grade":       "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D",
        "issues":      issues,
        "suggestions": suggestions,
    }


# ── ROUTES ────────────────────────────────────────────────────────────────

@router.post("/analyse")
def analyse_content(payload: ContentAnalysisRequest):
    """
    Full content analysis: SEO score, readability, keyword density,
    auto-excerpt, and improvement suggestions.
    """
    content = payload.content
    word_count  = count_words(content)
    sent_count  = count_sentences(content)
    reading_ease = flesch_reading_ease(content)
    keywords    = extract_keywords(content, top_n=8)
    seo         = seo_score(payload.title, content, payload.target_keyword)

    # Estimated reading time (avg 200 words/min)
    reading_time_min = math.ceil(word_count / 200)

    # Readability grade
    if reading_ease >= 70:
        readability_label = "Easy (suitable for general audience)"
    elif reading_ease >= 50:
        readability_label = "Standard (suitable for informed audience)"
    elif reading_ease >= 30:
        readability_label = "Difficult (technical audience)"
    else:
        readability_label = "Very difficult — consider simplifying"

    # Auto-generate excerpt from first 2 sentences
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    auto_excerpt = " ".join(sentences[:2])[:300]

    return {
        "word_count":       word_count,
        "sentence_count":   sent_count,
        "reading_time_min": reading_time_min,
        "reading_ease":     reading_ease,
        "readability":      readability_label,
        "top_keywords":     keywords,
        "auto_excerpt":     auto_excerpt,
        "seo":              seo,
        "keyword_density":  keyword_density(content, payload.target_keyword) if payload.target_keyword else None,
    }


@router.post("/suggest-tags")
def suggest_tags(payload: TagSuggestionRequest):
    """
    Suggest relevant tags based on title + content keyword extraction.
    In production: replace with a fine-tuned classifier or LLM call.
    """
    combined = f"{payload.title} {payload.content}"
    keywords = extract_keywords(combined, top_n=payload.max_tags * 2)

    # Filter: keep multi-word concepts if adjacent in title
    title_words = payload.title.lower().split()
    bigrams = [f"{title_words[i]} {title_words[i+1]}" for i in range(len(title_words)-1)]

    suggestions = list(dict.fromkeys(bigrams + keywords))[:payload.max_tags]

    return {
        "suggested_tags": suggestions,
        "note": "Review and select tags most relevant to your article.",
    }


@router.post("/headline-variants")
def generate_headline_variants(payload: HeadlineRequest):
    """
    Generate headline style variants for A/B testing.
    Uses template-based generation (replace with LLM in production).
    """
    topic = payload.topic.strip()
    topic_cap = topic.capitalize()

    variants = {
        "news": [
            f"{topic_cap}: Everything You Need to Know",
            f"What You Should Know About {topic_cap}",
            f"The Truth About {topic_cap}",
            f"{topic_cap}: A Complete Overview",
            f"Why {topic_cap} Matters More Than Ever",
        ],
        "listicle": [
            f"10 Things About {topic_cap} That Will Change How You Think",
            f"7 Key Facts About {topic_cap}",
            f"5 Reasons {topic_cap} Is More Important Than You Think",
            f"The Top 8 Insights on {topic_cap}",
            f"12 Things Experts Say About {topic_cap}",
        ],
        "how-to": [
            f"How to Understand {topic_cap} in 5 Minutes",
            f"A Beginner's Guide to {topic_cap}",
            f"How to Get Started With {topic_cap}",
            f"The Step-by-Step Guide to {topic_cap}",
            f"How to Master {topic_cap}: A Practical Guide",
        ],
        "question": [
            f"What Is {topic_cap} and Why Does It Matter?",
            f"Is {topic_cap} the Future?",
            f"Why Is Everyone Talking About {topic_cap}?",
            f"How Does {topic_cap} Actually Work?",
            f"What Are the Benefits of {topic_cap}?",
        ],
    }

    style = payload.style if payload.style in variants else "news"
    selected = variants[style]

    return {
        "topic":    topic,
        "style":    style,
        "variants": selected,
        "tip":      "A/B test at least 2 variants. Track CTR over 48 hours before picking a winner.",
    }


@router.get("/readability-tips")
def readability_tips():
    """General readability tips for content editors — useful for Publive's content teams."""
    return {
        "tips": [
            "Keep sentences under 20 words on average.",
            "Use active voice — 'The team built the feature' not 'The feature was built by the team'.",
            "Break content into sections with clear H2/H3 headings.",
            "Use bullet points for lists of 3 or more items.",
            "Front-load your most important information (inverted pyramid).",
            "Aim for a Flesch Reading Ease score above 60 for general audiences.",
            "Use the target keyword naturally — aim for 1–2% density.",
            "Include a compelling hook in the first 2 sentences.",
            "End with a clear call-to-action.",
        ]
    }
