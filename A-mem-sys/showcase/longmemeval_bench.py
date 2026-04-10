#!/usr/bin/env python3
"""
LongMemEval Synthetic Smoke Test for A-mem-sys
===============================================

12 hand-crafted instances covering all 5 LongMemEval abilities:
  - Information Extraction (single-session-user, single-session-assistant, single-session-preference)
  - Multi-Session Reasoning
  - Knowledge Updates
  - Temporal Reasoning
  - Abstention

Purpose: verify the retrieval pipeline is plumbed correctly and expose obvious
gaps (recency, abstention). NOT a publishable benchmark -- use longmemeval_real.py
for that.

Usage:
    .venv/bin/python showcase/longmemeval_bench.py
    .venv/bin/python showcase/longmemeval_bench.py --top-k 3 --verbose
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# A-mem-sys adapter (ChromaDB in-memory, sentence-transformers)
# ---------------------------------------------------------------------------


def _make_retriever(model_name: str = "all-MiniLM-L6-v2"):
    """Create an in-memory ChromaRetriever for benchmarking."""
    from agentic_memory.retrievers import ChromaRetriever

    return ChromaRetriever(
        model_name=model_name,
        embedding_backend="sentence-transformer",
    )


def flatten_session(turns: list[dict[str, str]]) -> str:
    """Flatten a session's turns into a single string."""
    return "\n".join(f"{t['role']}: {t['content']}" for t in turns)


def insert_sessions(retriever, sessions: list[list[dict]], session_ids: list[str]):
    """Batch-insert sessions into ChromaDB collection."""
    documents = [flatten_session(s) for s in sessions]
    metadatas = [{"session_id": sid} for sid in session_ids]
    retriever.collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=session_ids,
    )


def retrieve_session_ids(retriever, query: str, top_k: int) -> list[tuple[str, float]]:
    """Retrieve top-k session IDs with scores."""
    results = retriever.search(query, k=top_k)
    ids = results["ids"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]
    out = []
    for i, meta in enumerate(metadatas):
        sid = meta.get("session_id", ids[i]) if isinstance(meta, dict) else ids[i]
        out.append((sid, distances[i]))
    return out


# ---------------------------------------------------------------------------
# Synthetic seed data (12 instances)
# ---------------------------------------------------------------------------


def _s(role: str, content: str) -> dict:
    """Shorthand for a turn dict."""
    return {"role": role, "content": content}


def _build_seeds() -> list[dict[str, Any]]:
    """Build 12 hand-crafted LongMemEval-format instances."""
    seeds = []

    # ---- 1. single-session-user: specific fact buried in a cooking session ----
    seeds.append(
        {
            "question_id": "synth_001",
            "question_type": "single-session-user",
            "question": "What spice does my grandmother use in her apple pie instead of cinnamon?",
            "answer": "cardamom",
            "haystack_session_ids": [f"s1_{i}" for i in range(10)],
            "answer_session_ids": ["s1_3"],
            "haystack_sessions": [
                # s1_0: general baking
                [
                    _s("user", "I've been trying to bake more at home recently."),
                    _s(
                        "assistant",
                        "That's great! What kind of baking are you interested in?",
                    ),
                    _s(
                        "user",
                        "Mostly bread and cookies. I love the smell of fresh bread.",
                    ),
                ],
                # s1_1: recipe for banana bread
                [
                    _s("user", "Can you give me a good banana bread recipe?"),
                    _s(
                        "assistant",
                        "Sure! You'll need 3 ripe bananas, 1/3 cup melted butter, 3/4 cup sugar, 1 egg, 1 tsp vanilla, 1 tsp baking soda, pinch of salt, and 1.5 cups flour.",
                    ),
                    _s("user", "Should I add any spices?"),
                    _s(
                        "assistant",
                        "Cinnamon and nutmeg work well in banana bread. Try half a teaspoon of each.",
                    ),
                ],
                # s1_2: sourdough discussion
                [
                    _s(
                        "user",
                        "I started a sourdough starter last week but it's not rising.",
                    ),
                    _s(
                        "assistant",
                        "How often are you feeding it? Temperature also matters a lot.",
                    ),
                    _s("user", "Once a day, and my kitchen is around 68 degrees."),
                    _s(
                        "assistant",
                        "Try feeding twice a day and keeping it somewhere warmer, like on top of the fridge.",
                    ),
                ],
                # s1_3: EVIDENCE - grandmother's apple pie with cardamom
                [
                    _s(
                        "user",
                        "I want to make an apple pie this weekend for my family gathering.",
                    ),
                    _s(
                        "assistant",
                        "Apple pie is a classic! Do you have a recipe in mind?",
                    ),
                    _s(
                        "user",
                        "Yes, my grandmother's recipe is special. She always used cardamom instead of cinnamon, and it gives it this unique warm flavor that everyone loves.",
                    ),
                    _s(
                        "assistant",
                        "That's a wonderful twist! Cardamom pairs beautifully with apples. How much does she typically use?",
                    ),
                    _s(
                        "user",
                        "About a teaspoon for a standard pie. She also adds a splash of vanilla extract.",
                    ),
                ],
                # s1_4: kitchen equipment
                [
                    _s("user", "I need a new stand mixer. Any recommendations?"),
                    _s(
                        "assistant",
                        "KitchenAid Artisan is the most popular choice. The Breville Scraper Mixer Pro is also excellent.",
                    ),
                    _s("user", "What's the price range?"),
                    _s(
                        "assistant",
                        "KitchenAid Artisan runs about $350-400, the Breville around $300.",
                    ),
                ],
                # s1_5: chocolate chip cookies
                [
                    _s("user", "What's the secret to perfect chocolate chip cookies?"),
                    _s(
                        "assistant",
                        "Brown butter, a mix of bread and all-purpose flour, and chilling the dough for 24-36 hours.",
                    ),
                    _s("user", "I never thought about chilling that long."),
                    _s(
                        "assistant",
                        "It lets the flour fully hydrate and develops deeper flavor.",
                    ),
                ],
                # s1_6: holiday baking
                [
                    _s("user", "I'm planning my holiday baking list."),
                    _s("assistant", "What traditions does your family have?"),
                    _s(
                        "user",
                        "We usually make gingerbread, sugar cookies, and a yule log.",
                    ),
                    _s(
                        "assistant",
                        "Those are wonderful choices. Do you need any recipes?",
                    ),
                ],
                # s1_7: gluten free baking
                [
                    _s(
                        "user",
                        "My friend has celiac disease. What flour alternatives work for baking?",
                    ),
                    _s(
                        "assistant",
                        "King Arthur's gluten-free 1-to-1 flour is reliable. Almond flour and oat flour also work well for certain recipes.",
                    ),
                ],
                # s1_8: pie crust tips
                [
                    _s(
                        "user",
                        "My pie crusts always turn out tough. What am I doing wrong?",
                    ),
                    _s(
                        "assistant",
                        "You're likely overworking the dough. Keep butter very cold, use ice water, and handle it as little as possible.",
                    ),
                    _s("user", "Should I use butter or shortening?"),
                    _s(
                        "assistant",
                        "Butter for flavor, or a 50/50 mix for flakiness and taste.",
                    ),
                ],
                # s1_9: bread flour discussion
                [
                    _s(
                        "user",
                        "What's the difference between bread flour and all-purpose?",
                    ),
                    _s(
                        "assistant",
                        "Bread flour has higher protein content (12-14% vs 10-12%), giving more gluten development and chewier texture.",
                    ),
                ],
            ],
        }
    )

    # ---- 2. single-session-assistant: specific recommendation ----
    seeds.append(
        {
            "question_id": "synth_002",
            "question_type": "single-session-assistant",
            "question": "What three stretches did you recommend for my lower back pain?",
            "answer": "cat-cow, child's pose, and piriformis stretch",
            "haystack_session_ids": [f"s2_{i}" for i in range(10)],
            "answer_session_ids": ["s2_5"],
            "haystack_sessions": [
                [
                    _s(
                        "user",
                        "I've been sitting at my desk too much and my neck is stiff.",
                    ),
                    _s(
                        "assistant",
                        "Try doing neck rolls and chin tucks every hour. Also ensure your monitor is at eye level.",
                    ),
                ],
                [
                    _s("user", "What's a good workout routine for beginners?"),
                    _s(
                        "assistant",
                        "Start with 3 days per week: push-ups, squats, lunges, and planks. 3 sets of 10 reps each.",
                    ),
                ],
                [
                    _s("user", "How many steps should I aim for daily?"),
                    _s(
                        "assistant",
                        "10,000 steps is a common goal, but even 7,000 provides significant health benefits.",
                    ),
                ],
                [
                    _s("user", "My shoulders feel tight from sleeping on my side."),
                    _s(
                        "assistant",
                        "Try the doorway stretch and cross-body arm stretch. Also consider a better pillow.",
                    ),
                ],
                [
                    _s("user", "I want to start running. How do I avoid shin splints?"),
                    _s(
                        "assistant",
                        "Start with a walk-run program, increase mileage by no more than 10% per week, and get proper running shoes.",
                    ),
                ],
                # s2_5: EVIDENCE
                [
                    _s(
                        "user",
                        "I've had persistent lower back pain for the past two weeks. It's worst in the morning.",
                    ),
                    _s(
                        "assistant",
                        "Morning back pain is often related to sleep position and core strength. I'd recommend three specific stretches to start with.",
                    ),
                    _s("user", "What stretches?"),
                    _s(
                        "assistant",
                        "Try these three: cat-cow for spinal mobility, child's pose for gentle lower back release, and the piriformis stretch to address hip tightness that often contributes to lower back pain. Do each for 30 seconds, twice a day.",
                    ),
                    _s("user", "How long before I should see improvement?"),
                    _s(
                        "assistant",
                        "If you're consistent, usually 1-2 weeks. If it doesn't improve, see a physical therapist.",
                    ),
                ],
                [
                    _s("user", "Is yoga good for flexibility?"),
                    _s(
                        "assistant",
                        "Yes, yoga is excellent for flexibility and mobility. Start with beginner classes focusing on basic poses.",
                    ),
                ],
                [
                    _s("user", "How do I strengthen my core without sit-ups?"),
                    _s(
                        "assistant",
                        "Planks, dead bugs, bird dogs, and pallof presses are all great core exercises that are spine-friendly.",
                    ),
                ],
                [
                    _s("user", "I pulled a muscle in my hamstring while gardening."),
                    _s(
                        "assistant",
                        "Rest, ice, and gentle stretching. Avoid any exercises that cause sharp pain for at least a week.",
                    ),
                ],
                [
                    _s("user", "What's the best way to improve posture?"),
                    _s(
                        "assistant",
                        "Strengthen your upper back and core. Practice wall angels and consider a standing desk for part of the day.",
                    ),
                ],
            ],
        }
    )

    # ---- 3. single-session-preference: opinion about horror movies ----
    seeds.append(
        {
            "question_id": "synth_003",
            "question_type": "single-session-preference",
            "question": "How do I feel about horror movies?",
            "answer": "dislikes them, they give nightmares for days",
            "haystack_session_ids": [f"s3_{i}" for i in range(8)],
            "answer_session_ids": ["s3_2"],
            "haystack_sessions": [
                [
                    _s(
                        "user",
                        "I just watched The Shawshank Redemption again. It never gets old.",
                    ),
                    _s(
                        "assistant",
                        "It's consistently rated one of the best films ever. What do you love most about it?",
                    ),
                    _s(
                        "user",
                        "The story of hope and perseverance. Tim Robbins was perfect.",
                    ),
                ],
                [
                    _s("user", "Can you recommend some good sci-fi movies?"),
                    _s(
                        "assistant",
                        "Arrival, Interstellar, and Blade Runner 2049 are all excellent.",
                    ),
                    _s(
                        "user",
                        "I've seen Interstellar but not the other two. I'll check them out.",
                    ),
                ],
                # s3_2: EVIDENCE
                [
                    _s(
                        "user",
                        "My friends keep inviting me to see the latest horror movie, but I really can't stand them.",
                    ),
                    _s(
                        "assistant",
                        "Horror isn't for everyone. What is it about them that bothers you?",
                    ),
                    _s(
                        "user",
                        "They give me nightmares for days. Even the trailers make me uncomfortable. I just can't handle the jump scares and the creepy imagery.",
                    ),
                    _s(
                        "assistant",
                        "That's completely valid. You could suggest alternative movie genres when your friends invite you.",
                    ),
                ],
                [
                    _s("user", "What's a good movie to watch on a date night?"),
                    _s(
                        "assistant",
                        "Romantic comedies like When Harry Met Sally or more modern picks like Crazy Rich Asians work well.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "I heard the new Marvel movie is out. Is it worth seeing?",
                    ),
                    _s(
                        "assistant",
                        "If you enjoy the MCU, it's entertaining but not as strong as some earlier entries.",
                    ),
                ],
                [
                    _s("user", "I love documentaries about nature. Any suggestions?"),
                    _s(
                        "assistant",
                        "Planet Earth series, Our Planet, and Blue Planet are all stunning.",
                    ),
                ],
                [
                    _s("user", "What streaming service has the best movie selection?"),
                    _s(
                        "assistant",
                        "It depends on your taste. Netflix has variety, Criterion has classics, and Disney+ dominates family content.",
                    ),
                ],
                [
                    _s("user", "I'm looking for a feel-good movie for tonight."),
                    _s(
                        "assistant",
                        "Try The Secret Life of Walter Mitty, Chef, or Paddington 2. All uplifting and fun.",
                    ),
                ],
            ],
        }
    )

    # ---- 4. single-session-user: pet breed buried in a vet visit discussion ----
    seeds.append(
        {
            "question_id": "synth_004",
            "question_type": "single-session-user",
            "question": "What breed is my dog?",
            "answer": "Australian Shepherd",
            "haystack_session_ids": [f"s4_{i}" for i in range(8)],
            "answer_session_ids": ["s4_4"],
            "haystack_sessions": [
                [
                    _s(
                        "user",
                        "I need to buy pet food. What brand do you recommend for medium-sized dogs?",
                    ),
                    _s(
                        "assistant",
                        "Purina Pro Plan and Royal Canin are both well-regarded. Consider your dog's age and activity level.",
                    ),
                ],
                [
                    _s("user", "How often should I take my dog to the groomer?"),
                    _s(
                        "assistant",
                        "It depends on the breed and coat type. Generally every 4-8 weeks for most dogs.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "My neighbor's dog keeps barking at night. What can I do?",
                    ),
                    _s(
                        "assistant",
                        "You could talk to your neighbor politely about it. If it persists, check local noise ordinances.",
                    ),
                ],
                [
                    _s("user", "What are the best dog parks in the Portland area?"),
                    _s(
                        "assistant",
                        "Sellwood Riverfront Park, Gabriel Park, and the off-leash areas along the Willamette are popular.",
                    ),
                ],
                # s4_4: EVIDENCE
                [
                    _s(
                        "user",
                        "I need to schedule my dog's annual checkup. He's been scratching a lot lately.",
                    ),
                    _s(
                        "assistant",
                        "Excessive scratching could be allergies, fleas, or a skin condition. What breed is your dog?",
                    ),
                    _s(
                        "user",
                        "He's an Australian Shepherd, about 3 years old. His name is Cooper.",
                    ),
                    _s(
                        "assistant",
                        "Aussies can be prone to skin allergies. The vet should check for environmental allergies and maybe do a skin scraping.",
                    ),
                    _s("user", "He's also been chewing on his paws."),
                    _s(
                        "assistant",
                        "Paw chewing often indicates allergies too. In the meantime, you could try wiping his paws after walks.",
                    ),
                ],
                [
                    _s("user", "Should I get pet insurance?"),
                    _s(
                        "assistant",
                        "It can be worthwhile, especially for breeds prone to health issues. Lemonade and Healthy Paws are popular options.",
                    ),
                ],
                [
                    _s("user", "How much exercise does a herding dog need daily?"),
                    _s(
                        "assistant",
                        "At least 1-2 hours of vigorous exercise. Mental stimulation is equally important -- try puzzle toys and training sessions.",
                    ),
                ],
                [
                    _s("user", "My dog is afraid of thunderstorms. What can I help?"),
                    _s(
                        "assistant",
                        "Create a safe space, use white noise, and consider a ThunderShirt. In severe cases, talk to your vet about anti-anxiety options.",
                    ),
                ],
            ],
        }
    )

    # ---- 5. multi-session: programming languages across sessions ----
    seeds.append(
        {
            "question_id": "synth_005",
            "question_type": "multi-session",
            "question": "What programming languages do I know and what am I currently learning?",
            "answer": "Knows Python (5 years) and JavaScript; currently learning Rust",
            "haystack_session_ids": [f"s5_{i}" for i in range(10)],
            "answer_session_ids": ["s5_1", "s5_6"],
            "haystack_sessions": [
                [
                    _s(
                        "user",
                        "I need help setting up a new development environment on my Mac.",
                    ),
                    _s(
                        "assistant",
                        "What tools and languages do you primarily work with?",
                    ),
                    _s("user", "I use VS Code mostly, with Docker for containers."),
                ],
                # s5_1: EVIDENCE - Python and JavaScript experience
                [
                    _s("user", "I'm building a web scraping tool for my company."),
                    _s("assistant", "What language are you using?"),
                    _s(
                        "user",
                        "Python. I've been using it for about 5 years now, mostly for data analysis and backend work. I also know JavaScript for frontend stuff.",
                    ),
                    _s(
                        "assistant",
                        "Great, Python has excellent libraries for web scraping. BeautifulSoup and Scrapy are popular choices.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "How do I optimize my PostgreSQL queries? They're running slow.",
                    ),
                    _s(
                        "assistant",
                        "Start with EXPLAIN ANALYZE to identify bottlenecks. Add indexes on frequently queried columns.",
                    ),
                ],
                [
                    _s("user", "What's the best way to deploy a microservice?"),
                    _s(
                        "assistant",
                        "Docker + Kubernetes is the standard stack. For simpler setups, Docker Compose works well.",
                    ),
                ],
                [
                    _s("user", "I'm having trouble with async/await in my code."),
                    _s(
                        "assistant",
                        "Are you working with asyncio in Python or Promises in JavaScript?",
                    ),
                    _s("user", "Asyncio. I keep getting event loop errors."),
                    _s(
                        "assistant",
                        "Make sure you're not calling asyncio.run() inside an existing loop. Use await instead.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "Can you explain the difference between REST and GraphQL?",
                    ),
                    _s(
                        "assistant",
                        "REST uses fixed endpoints for resources, GraphQL lets clients request exactly the data they need with a single endpoint.",
                    ),
                ],
                # s5_6: EVIDENCE - learning Rust
                [
                    _s(
                        "user",
                        "I've decided to pick up a systems programming language.",
                    ),
                    _s(
                        "assistant",
                        "That's a great idea. C, C++, and Rust are the main options.",
                    ),
                    _s(
                        "user",
                        "I'm going with Rust. I've been working through The Rust Book this past month. The borrow checker is challenging but I'm starting to get the hang of ownership.",
                    ),
                    _s(
                        "assistant",
                        "Rust's learning curve is steep but worth it. The memory safety guarantees are invaluable.",
                    ),
                ],
                [
                    _s("user", "How do I set up CI/CD for my project?"),
                    _s(
                        "assistant",
                        "GitHub Actions is straightforward. Create a workflow YAML file in .github/workflows/.",
                    ),
                ],
                [
                    _s("user", "What's the best database for time-series data?"),
                    _s(
                        "assistant",
                        "TimescaleDB (PostgreSQL extension), InfluxDB, and QuestDB are all strong choices.",
                    ),
                ],
                [
                    _s("user", "I need to learn more about design patterns."),
                    _s(
                        "assistant",
                        "Start with the Gang of Four book, then look at language-specific patterns. Factory, Observer, and Strategy are the most commonly used.",
                    ),
                ],
            ],
        }
    )

    # ---- 6. multi-session: daughter's name in one session, piano in another ----
    seeds.append(
        {
            "question_id": "synth_006",
            "question_type": "multi-session",
            "question": "What instrument did my daughter start learning and how old is she?",
            "answer": "Piano, she is 6 years old",
            "haystack_session_ids": [f"s6_{i}" for i in range(10)],
            "answer_session_ids": ["s6_1", "s6_7"],
            "haystack_sessions": [
                [
                    _s(
                        "user",
                        "I'm looking for activities for kids in the Denver area.",
                    ),
                    _s(
                        "assistant",
                        "There are lots of options! Sports leagues, art classes, museums, and outdoor activities like hiking.",
                    ),
                ],
                # s6_1: EVIDENCE - daughter Sophie, age 6
                [
                    _s(
                        "user",
                        "I need advice about my daughter Sophie's school situation.",
                    ),
                    _s("assistant", "Of course. What's going on?"),
                    _s(
                        "user",
                        "She's 6 and just started first grade. Her teacher says she's struggling with reading but excels at math.",
                    ),
                    _s(
                        "assistant",
                        "That's not uncommon. Some children develop reading skills a bit later. Consider reading together daily for 20 minutes.",
                    ),
                ],
                [
                    _s("user", "What are good birthday party themes for girls?"),
                    _s(
                        "assistant",
                        "Unicorn, space, dinosaur, superhero, and art party themes are all popular for kids.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "How much screen time is appropriate for young children?",
                    ),
                    _s(
                        "assistant",
                        "The AAP recommends no more than 1 hour per day of quality programming for children ages 2-5, with co-viewing.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "I want to start a college savings fund. What are my options?",
                    ),
                    _s(
                        "assistant",
                        "529 plans are the most popular. They offer tax advantages and can be used for tuition, room and board, and supplies.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "What's a good age to start teaching kids to ride a bike?",
                    ),
                    _s(
                        "assistant",
                        "Most children can learn between ages 4-6. Start with a balance bike to build confidence.",
                    ),
                ],
                [
                    _s("user", "My kids love crafts. What are some easy projects?"),
                    _s(
                        "assistant",
                        "Paper plate animals, painted rocks, friendship bracelets, and simple origami are all great options.",
                    ),
                ],
                # s6_7: EVIDENCE - Sophie started piano
                [
                    _s(
                        "user",
                        "We finally signed Sophie up for music lessons. She had her first one yesterday!",
                    ),
                    _s(
                        "assistant", "That's wonderful! What instrument did she choose?"
                    ),
                    _s(
                        "user",
                        "Piano. She was so excited. The teacher said she has a natural sense of rhythm.",
                    ),
                    _s(
                        "assistant",
                        "Piano is a great foundation for music. Make sure she has access to practice at home, even a small keyboard works.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "How do I encourage good study habits in young children?",
                    ),
                    _s(
                        "assistant",
                        "Create a consistent routine, a quiet study space, and make learning fun with games and hands-on activities.",
                    ),
                ],
                [
                    _s("user", "What are the best children's books for early readers?"),
                    _s(
                        "assistant",
                        "Dr. Seuss, Mo Willems' Elephant and Piggie series, and the Magic Tree House series are excellent.",
                    ),
                ],
            ],
        }
    )

    # ---- 7. multi-session: puppy adoption details across sessions ----
    seeds.append(
        {
            "question_id": "synth_007",
            "question_type": "multi-session",
            "question": "What is the name and breed of the puppy I recently adopted?",
            "answer": "Luna, a Golden Retriever mix",
            "haystack_session_ids": [f"s7_{i}" for i in range(8)],
            "answer_session_ids": ["s7_2", "s7_5"],
            "haystack_sessions": [
                [
                    _s(
                        "user",
                        "I'm thinking about adopting a pet from the local shelter.",
                    ),
                    _s(
                        "assistant",
                        "That's a wonderful idea! Are you considering a dog or a cat?",
                    ),
                    _s(
                        "user",
                        "Definitely a dog. I have a big backyard and love hiking.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "What should I prepare before bringing home a new puppy?",
                    ),
                    _s(
                        "assistant",
                        "You'll need food and water bowls, a crate, leash and collar, toys, puppy food, and pet pads for house training.",
                    ),
                ],
                # s7_2: EVIDENCE - adopted Luna
                [
                    _s(
                        "user",
                        "I went to the shelter yesterday and fell in love with the sweetest puppy!",
                    ),
                    _s("assistant", "That's exciting! Tell me about them."),
                    _s(
                        "user",
                        "Her name is Luna. She's about 4 months old and they said she's a Golden Retriever mix. She was so friendly and immediately came up to me.",
                    ),
                    _s(
                        "assistant",
                        "Luna sounds lovely! Golden Retriever mixes tend to be very affectionate and great with families.",
                    ),
                ],
                [
                    _s("user", "How do I house train a puppy?"),
                    _s(
                        "assistant",
                        "Take them out every 2 hours, after meals, after naps, and after play. Praise and treat immediately after they go outside.",
                    ),
                ],
                [
                    _s("user", "What vaccines does a puppy need?"),
                    _s(
                        "assistant",
                        "Core vaccines include distemper, parvovirus, hepatitis, and rabies. Your vet will set up a schedule.",
                    ),
                ],
                # s7_5: EVIDENCE - Luna's first vet visit
                [
                    _s(
                        "user",
                        "Luna had her first vet visit today. The vet said she's healthy and estimated she's a Golden Retriever and Lab mix.",
                    ),
                    _s(
                        "assistant",
                        "That's great news! Golden Lab mixes are known for being gentle and trainable. Did they set up a vaccine schedule?",
                    ),
                    _s(
                        "user",
                        "Yes, she needs two more rounds of shots over the next month.",
                    ),
                ],
                [
                    _s("user", "What's the best puppy food brand?"),
                    _s(
                        "assistant",
                        "Purina Pro Plan Puppy, Royal Canin, and Hill's Science Diet are all well-regarded for puppies.",
                    ),
                ],
                [
                    _s("user", "How do I stop my puppy from chewing on furniture?"),
                    _s(
                        "assistant",
                        "Redirect to appropriate chew toys, use bitter apple spray on furniture, and ensure they have enough mental stimulation.",
                    ),
                ],
            ],
        }
    )

    # ---- 8. knowledge-update: workplace changed ----
    seeds.append(
        {
            "question_id": "synth_008",
            "question_type": "knowledge-update",
            "question": "Where do I currently work?",
            "answer": "Meta",
            "haystack_session_ids": [f"s8_{i}" for i in range(10)],
            "answer_session_ids": ["s8_7"],
            "haystack_sessions": [
                [
                    _s("user", "I'm dealing with a difficult coworker situation."),
                    _s("assistant", "What's happening?"),
                    _s("user", "They keep taking credit for my work in meetings."),
                    _s(
                        "assistant",
                        "Document your contributions and address it with your manager privately.",
                    ),
                ],
                [
                    _s("user", "How do I negotiate a raise?"),
                    _s(
                        "assistant",
                        "Research market rates, document your achievements, and schedule a meeting with your manager. Practice your talking points.",
                    ),
                ],
                # s8_2: OLD fact - works at Google
                [
                    _s(
                        "user",
                        "I've been at Google for three years now as a software engineer.",
                    ),
                    _s("assistant", "That's a great run! How are you finding it?"),
                    _s(
                        "user",
                        "The work is interesting but the bureaucracy has been increasing. I'm on the Maps team.",
                    ),
                    _s(
                        "assistant",
                        "Large companies tend to add process over time. Is there a specific project you're passionate about?",
                    ),
                ],
                [
                    _s(
                        "user",
                        "What's the best way to prepare for a technical interview?",
                    ),
                    _s(
                        "assistant",
                        "Practice LeetCode problems, review system design concepts, and do mock interviews. Focus on your weak areas.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "I'm thinking about going back to school for a master's degree. Worth it?",
                    ),
                    _s(
                        "assistant",
                        "It depends on your goals. For career advancement in engineering, experience often matters more than a degree.",
                    ),
                ],
                [
                    _s("user", "How do I deal with burnout at work?"),
                    _s(
                        "assistant",
                        "Take regular breaks, set boundaries, use your PTO, and consider talking to a therapist. Exercise and hobbies outside work help too.",
                    ),
                ],
                [
                    _s("user", "What are the top tech companies to work for?"),
                    _s(
                        "assistant",
                        "Google, Apple, Meta, Microsoft, and Netflix consistently rank high. Smaller companies like Stripe and Databricks are also excellent.",
                    ),
                ],
                # s8_7: EVIDENCE - now works at Meta
                [
                    _s(
                        "user",
                        "Big news! I just started my new job at Meta last week. I'm on the Reality Labs team working on AR glasses.",
                    ),
                    _s(
                        "assistant",
                        "Congratulations! That sounds like a fascinating role. How's the transition from Google going?",
                    ),
                    _s(
                        "user",
                        "It's been smooth so far. The culture is different but I'm excited about the AR/VR space.",
                    ),
                    _s(
                        "assistant",
                        "Reality Labs is doing cutting-edge work. Enjoy the new challenge!",
                    ),
                ],
                [
                    _s(
                        "user",
                        "How do I make a good impression in the first 90 days of a new job?",
                    ),
                    _s(
                        "assistant",
                        "Listen more than you talk, ask questions, meet as many people as possible, and find early wins to build credibility.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "What certifications are valuable for software engineers?",
                    ),
                    _s(
                        "assistant",
                        "AWS certifications are popular. Google Cloud and Azure certs are also valued. For specific domains, consider Kubernetes (CKA) or security (CISSP).",
                    ),
                ],
            ],
        }
    )

    # ---- 9. knowledge-update: favorite language changed ----
    seeds.append(
        {
            "question_id": "synth_009",
            "question_type": "knowledge-update",
            "question": "What is my favorite programming language now?",
            "answer": "TypeScript",
            "haystack_session_ids": [f"s9_{i}" for i in range(8)],
            "answer_session_ids": ["s9_5"],
            "haystack_sessions": [
                [
                    _s("user", "What text editor do you think is best for coding?"),
                    _s(
                        "assistant",
                        "VS Code is the most popular. Neovim and JetBrains IDEs are also excellent depending on your workflow.",
                    ),
                ],
                # s9_1: OLD fact - favorite is JavaScript
                [
                    _s(
                        "user",
                        "I've been coding in JavaScript for 8 years and it's still my absolute favorite language.",
                    ),
                    _s(
                        "assistant",
                        "JavaScript's ecosystem is massive. What do you like most about it?",
                    ),
                    _s(
                        "user",
                        "The flexibility and how quickly you can build things. Node.js made it possible to use it everywhere.",
                    ),
                ],
                [
                    _s("user", "How do I set up ESLint for my project?"),
                    _s(
                        "assistant",
                        "Run npm init @eslint/config and follow the prompts. Choose the recommended rules as a starting point.",
                    ),
                ],
                [
                    _s("user", "What frontend framework should I learn?"),
                    _s(
                        "assistant",
                        "React has the largest ecosystem, Vue is easier to learn, and Svelte is gaining momentum.",
                    ),
                ],
                [
                    _s("user", "How do I handle errors properly in async code?"),
                    _s(
                        "assistant",
                        "Always use try/catch with async/await, or .catch() with promises. Never leave promises unhandled.",
                    ),
                ],
                # s9_5: EVIDENCE - switched to TypeScript
                [
                    _s(
                        "user",
                        "I have to say, after working with TypeScript for the past year, I've completely switched over. I can't imagine going back to plain JavaScript.",
                    ),
                    _s(
                        "assistant",
                        "TypeScript's type system does catch a lot of bugs at compile time. What convinced you?",
                    ),
                    _s(
                        "user",
                        "The IDE support is incredible. Autocomplete, refactoring, and catching errors before runtime. It's now my favorite language without question.",
                    ),
                    _s(
                        "assistant",
                        "Many developers share that experience. The initial investment in learning types pays off quickly.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "What build tools do you recommend for a modern web project?",
                    ),
                    _s(
                        "assistant",
                        "Vite is the current favorite for its speed. Webpack is still widely used. esbuild and Turbopack are also emerging options.",
                    ),
                ],
                [
                    _s("user", "How do I publish an npm package?"),
                    _s(
                        "assistant",
                        "Create a package.json, set up your entry point, run npm login, then npm publish. Consider using np for a smoother workflow.",
                    ),
                ],
            ],
        }
    )

    # ---- 10. temporal-reasoning: car purchase then service ----
    seeds.append(
        {
            "question_id": "synth_010",
            "question_type": "temporal-reasoning",
            "question": "What issue came up with the car I bought in January when I took it for its first service?",
            "answer": "A software update was needed for the infotainment system, and a minor recall on the brake sensors",
            "haystack_session_ids": [f"s10_{i}" for i in range(10)],
            "answer_session_ids": ["s10_2", "s10_7"],
            "haystack_sessions": [
                [
                    _s(
                        "user",
                        "I'm thinking about buying a new car. Electric or hybrid?",
                    ),
                    _s(
                        "assistant",
                        "It depends on your driving habits. If you mostly do city driving and can charge at home, electric is great. For longer trips, hybrid gives peace of mind.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "What's the difference between Tesla Model 3 and Model Y?",
                    ),
                    _s(
                        "assistant",
                        "Model Y is an SUV with more cargo space and higher ride height. Model 3 is a sedan, slightly cheaper and sportier to drive.",
                    ),
                ],
                # s10_2: EVIDENCE - bought Tesla Model 3 in January
                [
                    _s(
                        "user",
                        "I finally did it! Just picked up my new Tesla Model 3 yesterday. Long Range, midnight blue.",
                    ),
                    _s(
                        "assistant",
                        "Congratulations! That's a great choice. How was the pickup experience?",
                    ),
                    _s(
                        "user",
                        "Smooth but a bit rushed. They showed me the basics and sent me on my way. The autopilot is amazing though.",
                    ),
                    _s(
                        "assistant",
                        "The Long Range gives you great flexibility. Make sure to set up the app for remote monitoring and preconditioning.",
                    ),
                ],
                [
                    _s("user", "How do I install a home EV charger?"),
                    _s(
                        "assistant",
                        "You'll need a 240V outlet or a hardwired NEMA 14-50 outlet. Hire a licensed electrician. The Tesla Wall Connector is the most convenient option.",
                    ),
                ],
                [
                    _s("user", "What's the best way to maintain an electric car?"),
                    _s(
                        "assistant",
                        "Rotate tires every 6,250 miles, check brake fluid every 2 years, replace cabin air filter yearly, and keep the battery between 20-80% for daily use.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "I'm planning a road trip from Portland to LA. How many charging stops will I need?",
                    ),
                    _s(
                        "assistant",
                        "In a Model 3 Long Range, you'll need about 3-4 Supercharger stops. The route along I-5 is well covered with Superchargers.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "My car insurance went up after buying the Tesla. Is that normal?",
                    ),
                    _s(
                        "assistant",
                        "Yes, Teslas tend to have higher insurance rates due to repair costs. Shop around -- GEICO and Progressive often have competitive Tesla rates.",
                    ),
                ],
                # s10_7: EVIDENCE - first service appointment issues
                [
                    _s(
                        "user",
                        "Took my Tesla in for its first service appointment today. It's been about 3 months since I got it.",
                    ),
                    _s("assistant", "How did it go?"),
                    _s(
                        "user",
                        "They found that the infotainment system needed a software update that couldn't be done over-the-air, and there's a minor recall on the brake sensors.",
                    ),
                    _s(
                        "assistant",
                        "Software updates and recalls are common in the first year. Did they fix everything same-day?",
                    ),
                    _s(
                        "user",
                        "Yes, it took about two hours. They were thorough about it.",
                    ),
                ],
                [
                    _s("user", "How do I find the nearest Supercharger?"),
                    _s(
                        "assistant",
                        "Use the Tesla app or the in-car navigation. It automatically routes through Superchargers on long trips.",
                    ),
                ],
                [
                    _s("user", "Is it worth getting paint protection film for my car?"),
                    _s(
                        "assistant",
                        "PPF is worth it on the front bumper, hood, and fenders. Expect to pay $1500-3000 for partial coverage.",
                    ),
                ],
            ],
        }
    )

    # ---- 11. temporal-reasoning: sequence of events with a home renovation ----
    seeds.append(
        {
            "question_id": "synth_011",
            "question_type": "temporal-reasoning",
            "question": "What problem did the contractor find during my kitchen renovation after the demolition was done?",
            "answer": "Water damage behind the old cabinets and outdated wiring that wasn't up to code",
            "haystack_session_ids": [f"s11_{i}" for i in range(8)],
            "answer_session_ids": ["s11_5"],
            "haystack_sessions": [
                [
                    _s(
                        "user",
                        "I'm thinking about renovating my kitchen. Where do I start?",
                    ),
                    _s(
                        "assistant",
                        "Start with a budget and priorities. Get 3 contractor quotes, visit showrooms for cabinets and countertops, and plan the layout.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "What countertop material should I choose? I'm torn between quartz and granite.",
                    ),
                    _s(
                        "assistant",
                        "Quartz is more uniform and maintenance-free. Granite has natural beauty but needs periodic sealing. Both are durable.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "We hired a contractor and demolition starts next week! So excited.",
                    ),
                    _s(
                        "assistant",
                        "Exciting! Make sure you have a plan for cooking during the renovation. It typically takes 6-12 weeks.",
                    ),
                    _s(
                        "user",
                        "We set up a temporary kitchen in the basement with a microwave and hot plate.",
                    ),
                ],
                [
                    _s("user", "How much does a kitchen renovation typically cost?"),
                    _s(
                        "assistant",
                        "A mid-range kitchen renovation runs $25,000-50,000. High-end can be $75,000+. Major factors are cabinets, countertops, and appliances.",
                    ),
                ],
                [
                    _s("user", "What appliance brands are the most reliable?"),
                    _s(
                        "assistant",
                        "Bosch for dishwashers, GE for ranges, LG for refrigerators. Avoid brands with high repair rates.",
                    ),
                ],
                # s11_5: EVIDENCE - problems found after demolition
                [
                    _s(
                        "user",
                        "The demolition is done but the contractor found some issues. Not great news.",
                    ),
                    _s("assistant", "What did they find?"),
                    _s(
                        "user",
                        "There's water damage behind where the old cabinets were, and the wiring is outdated and not up to current code. They said we need to rewire that section.",
                    ),
                    _s(
                        "assistant",
                        "That's unfortunately common in older homes. Water damage behind cabinets often goes unnoticed for years. How much does the rewiring add to the budget?",
                    ),
                    _s(
                        "user",
                        "About $4,000 for the electrical work and $2,000 for the water damage repairs. Our contingency fund should cover it.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "Should I go with an island or a peninsula in my kitchen?",
                    ),
                    _s(
                        "assistant",
                        "If you have the space (at least 36 inches clearance on all sides), an island is more versatile. Otherwise, a peninsula saves space.",
                    ),
                ],
                [
                    _s("user", "What color cabinets are trending for kitchens?"),
                    _s(
                        "assistant",
                        "White and navy are classic. Sage green and warm wood tones are trending. Two-tone (white uppers, dark lowers) is also popular.",
                    ),
                ],
            ],
        }
    )

    # ---- 12. abstention: cat breed (never mentioned) ----
    seeds.append(
        {
            "question_id": "synth_012_abs",
            "question_type": "single-session-user",
            "question": "What breed is my cat?",
            "answer": "",
            "haystack_session_ids": [f"s12_{i}" for i in range(8)],
            "answer_session_ids": [],
            "haystack_sessions": [
                [
                    _s(
                        "user",
                        "I need recommendations for indoor plants that are pet-safe.",
                    ),
                    _s(
                        "assistant",
                        "Spider plants, Boston ferns, and calatheas are all safe for pets. Avoid lilies, pothos, and philodendrons.",
                    ),
                ],
                [
                    _s("user", "How do I keep my house clean with pets?"),
                    _s(
                        "assistant",
                        "Vacuum frequently, use washable covers on furniture, and keep lint rollers handy. HEPA air purifiers help with dander.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "What's the best way to introduce a new pet to the household?",
                    ),
                    _s(
                        "assistant",
                        "Gradual introduction is key. Keep them in separate rooms initially, swap scents via bedding, and supervise all interactions.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "My pet has been losing more fur than usual. Should I be worried?",
                    ),
                    _s(
                        "assistant",
                        "Seasonal shedding is normal. If it's excessive or patchy, it could be stress, diet, or a medical issue. See your vet.",
                    ),
                ],
                [
                    _s("user", "What are some good puzzle toys for pets?"),
                    _s(
                        "assistant",
                        "Kong toys for dogs, treat-dispensing balls, and lick mats are all great. For mental stimulation, try snuffle mats.",
                    ),
                ],
                [
                    _s("user", "How often should I take my pet for a checkup?"),
                    _s(
                        "assistant",
                        "Annually for young, healthy pets. Twice a year for seniors or those with health conditions.",
                    ),
                ],
                [
                    _s(
                        "user",
                        "I'm going on vacation. Should I board my pet or get a pet sitter?",
                    ),
                    _s(
                        "assistant",
                        "Pet sitters are less stressful for most animals since they stay in their familiar environment. Rover and TrustedHousesitters are good options.",
                    ),
                ],
                [
                    _s("user", "What's the best pet insurance company?"),
                    _s(
                        "assistant",
                        "Healthy Paws, Embrace, and Lemonade are consistently rated well. Compare coverage limits and deductibles.",
                    ),
                ],
            ],
        }
    )

    return seeds


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_instance(
    retriever,
    instance: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    """Evaluate one instance. Returns metrics dict."""
    retriever.clear()

    sessions = instance["haystack_sessions"]
    session_ids = instance["haystack_session_ids"]
    evidence = set(instance["answer_session_ids"] or [])
    is_abstention = instance["question_id"].endswith("_abs")
    question = instance["question"]

    # Index
    t0 = time.time()
    insert_sessions(retriever, sessions, session_ids)
    t_index = time.time() - t0

    # Retrieve
    t0 = time.time()
    hits = retrieve_session_ids(retriever, question, top_k)
    t_retrieve = time.time() - t0

    retrieved_ids = [sid for sid, _score in hits]

    result: dict[str, Any] = {
        "question_id": instance["question_id"],
        "question_type": instance["question_type"],
        "question": question,
        "retrieved_ids": retrieved_ids,
        "retrieved_scores": [score for _, score in hits],
        "evidence_ids": list(evidence),
        "is_abstention": is_abstention,
        "latency_index_s": t_index,
        "latency_retrieve_s": t_retrieve,
    }

    if is_abstention:
        result["correct_refusal"] = len(retrieved_ids) == 0
        result["recall"] = None
        result["hit_at_1"] = None
    else:
        found = set(retrieved_ids) & evidence
        result["recall"] = len(found) / len(evidence) if evidence else 0.0
        result["hit_at_1"] = int(retrieved_ids[0] in evidence) if retrieved_ids else 0
        result["found_evidence"] = list(found)
        result["missed_evidence"] = list(evidence - found)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="LongMemEval synthetic smoke test for A-mem-sys"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of sessions to retrieve (default: 5)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="all-MiniLM-L6-v2",
        help="Embedding model name (default: all-MiniLM-L6-v2)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print per-instance detail"
    )
    args = parser.parse_args()

    print(f"LongMemEval Synthetic Smoke Test (A-mem-sys)")
    print(f"  Embedder: {args.model}")
    print(f"  Backend:  ChromaDB (in-memory)")
    print(f"  top_k:    {args.top_k}")
    print()

    # Load model once
    print("Loading embedding model...", end=" ", flush=True)
    t0 = time.time()
    retriever = _make_retriever(args.model)
    print(f"done ({time.time() - t0:.1f}s)")
    print()

    seeds = _build_seeds()
    results = []

    for i, instance in enumerate(seeds, 1):
        result = evaluate_instance(retriever, instance, args.top_k)
        results.append(result)

        status = ""
        if result["is_abstention"]:
            status = "REFUSAL " + ("OK" if result["correct_refusal"] else "FAIL")
        else:
            status = f"recall={result['recall']:.0%}  hit@1={result['hit_at_1']}"

        print(f"  [{i:2d}/{len(seeds)}] {result['question_type']:30s} {status}")

        if args.verbose:
            print(f"           Q: {result['question']}")
            print(f"           Evidence:  {result['evidence_ids']}")
            print(f"           Retrieved: {result['retrieved_ids']}")
            if not result["is_abstention"] and result.get("missed_evidence"):
                print(f"           Missed:    {result['missed_evidence']}")
            print()

    # ---- Aggregate metrics ----
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    answerable = [r for r in results if not r["is_abstention"]]
    abstention = [r for r in results if r["is_abstention"]]

    if answerable:
        avg_recall = sum(r["recall"] for r in answerable) / len(answerable)
        avg_hit1 = sum(r["hit_at_1"] for r in answerable) / len(answerable)
        avg_latency = sum(
            r["latency_index_s"] + r["latency_retrieve_s"] for r in answerable
        ) / len(answerable)

        print(f"\n  session_recall@{args.top_k}:  {avg_recall:.1%}")
        print(f"  session_hit@1:       {avg_hit1:.1%}")
        print(f"  Avg latency:         {avg_latency:.3f} s/instance")
        print(f"  Answerable:          {len(answerable)} instances")

    if abstention:
        refusal_rate = sum(1 for r in abstention if r["correct_refusal"]) / len(
            abstention
        )
        print(
            f"\n  Abstention refusal:  {refusal_rate:.0%}  ({len(abstention)} instances)"
        )

    # Per-type breakdown
    by_type = defaultdict(list)
    for r in answerable:
        by_type[r["question_type"]].append(r)

    if by_type:
        print(f"\n  {'Question Type':<35s} {'n':>4s}  {'recall':>7s}  {'hit@1':>7s}")
        print(f"  {'-' * 35} {'-' * 4}  {'-' * 7}  {'-' * 7}")
        for qtype in sorted(by_type.keys()):
            rs = by_type[qtype]
            n = len(rs)
            recall = sum(r["recall"] for r in rs) / n
            hit1 = sum(r["hit_at_1"] for r in rs) / n
            print(f"  {qtype:<35s} {n:4d}  {recall:6.1%}  {hit1:6.1%}")

    # Failures
    failures = [r for r in answerable if r["recall"] < 1.0]
    if failures:
        print(f"\n  Failures ({len(failures)}):")
        for r in failures:
            print(
                f"    {r['question_id']}: recall={r['recall']:.0%} | missed={r.get('missed_evidence', [])}"
            )
            print(f"      Q: {r['question']}")

    print()
    return 0 if (answerable and avg_recall >= 0.8) else 1


if __name__ == "__main__":
    sys.exit(main())
