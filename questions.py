"""Offline brainstorming questions. Edit freely: it's just data.

Each entry: (key, question, [4 options]). "{idea}" is replaced by the idea's title.
Used when no AI is configured, or when the AI is unreachable.
"""

QUESTIONS = [
    ("why", "Why does \"{idea}\" matter to you right now?", [
        "It would solve a problem I keep running into",
        "I'm simply curious and want to see what happens",
        "It supports a bigger goal I'm working toward",
        "Someone else would benefit from it"]),
    ("first_step", "What is the smallest first step you could take on \"{idea}\"?", [
        "Look up what already exists on this",
        "Sketch or write a one-page outline",
        "Try a tiny version with the data or tools I already have",
        "Talk it over with someone who knows the area"]),
    ("obstacle", "What is most likely to get in the way of \"{idea}\"?", [
        "Not enough time",
        "Missing knowledge or skills",
        "Missing data, tools or money",
        "I'm not sure what 'done' looks like"]),
    ("success", "How would you know \"{idea}\" worked?", [
        "I could show a clear result or number",
        "Someone else would say it was useful or good",
        "I'd feel the problem was gone",
        "It would lead to a better follow-up idea"]),
    ("simplest", "If you had one hour, what would the simplest version of \"{idea}\" be?", [
        "A rough prototype that barely works",
        "A written plan with next steps",
        "A quick experiment to test the riskiest part",
        "A conversation to find out if it is worth doing"]),
    ("assumption", "What are you assuming is true about \"{idea}\" that you haven't checked?", [
        "That the data or materials I need exist",
        "That it's actually new or hasn't been done",
        "That I can do it with the time I have",
        "That other people care about it"]),
    ("opposite", "What if the opposite of \"{idea}\" were the better idea?", [
        "I'd drop it and do the opposite approach",
        "I'd combine both and compare them",
        "I'd realise the opposite is simply easier",
        "It wouldn't change anything, the idea holds up"]),
    ("connect", "Which of your other ideas does \"{idea}\" feel closest to?", [
        "One I've already started working on",
        "One I had a long time ago",
        "None, this is genuinely a new direction",
        "I'm not sure, I'd need to look through them"]),
    ("who", "Who else should hear about \"{idea}\"?", [
        "A teammate or collaborator",
        "A mentor or expert",
        "A friend who'd tell me honestly",
        "Nobody yet, I need to think it through alone first"]),
    ("regret", "If you never did \"{idea}\", what would you miss?", [
        "A chance to learn something new",
        "A result I could share",
        "A better way of doing something I do often",
        "Honestly, not much, it may not be worth it"]),
    ("resources", "What is the one thing you'd need most to start \"{idea}\"?", [
        "Uninterrupted time",
        "A key piece of information",
        "A tool, dataset or material",
        "Someone's help or permission"]),
    ("grow", "Where could \"{idea}\" go if it went really well?", [
        "It becomes a bigger project",
        "It spawns several smaller follow-up ideas",
        "It becomes a habit or routine",
        "It stays small, and that's fine"]),
    ("priority", "How urgent is \"{idea}\" compared with the rest of your list?", [
        "Do it soon, it is time-sensitive",
        "Someday, but I don't want to forget it",
        "It depends on something else happening first",
        "I'm not sure it deserves a place on the list"]),
    ("feeling", "How do you feel when you imagine working on \"{idea}\"?", [
        "Excited, I want to start now",
        "Calm and curious",
        "A bit daunted by the size of it",
        "Nothing much, which tells me something"]),
]
