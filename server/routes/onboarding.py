"""
Onboarding Routes — first-time setup and returning user greeting.
Handles the scripted conversation flow before the AI is connected.
"""

import json
import server.state as state
from core.harness.persona import load_persona, save_persona, is_first_run


# Onboarding steps for first-time users
ONBOARDING_STEPS = [
    {
        "id": "welcome",
        "agent_text": "Welcome to **DeepDive** — your AI-powered OSINT investigation platform.\n\nI'm going to be your personal investigator. Before we get started, I need to know a couple things.",
        "wait_for": None,  # No input needed, auto-advance
    },
    {
        "id": "ask_user_name",
        "agent_text": "What should I call you?",
        "wait_for": "user_name",
        "placeholder": "Enter your name...",
    },
    {
        "id": "ask_agent_name",
        "agent_text": "Great, {user_name}. Now — what do you want to call me? I can be anyone. Sherlock, Sam, Nova, whatever you like.",
        "wait_for": "agent_name",
        "placeholder": "Name your investigator...",
    },
    {
        "id": "confirm",
        "agent_text": "Alright, {user_name}. I'm **{agent_name}**, your investigator. Here's what I can do:\n\n- **Investigate** anyone or anything — people, companies, events\n- **Search** 21+ OSINT data sources (news, SEC, sanctions, dark web, and more)\n- **Build graphs** mapping connections between entities\n- **Trace money**, timelines, social media, and archived content\n- **Generate reports** with detailed intelligence briefs\n- **Analyze documents** you point me to\n\nJust talk to me naturally. Tell me what you want to investigate and I'll handle the rest.\n\nReady to start your first investigation?",
        "wait_for": None,
    },
]


def get_onboarding_state():
    """Get the current onboarding state. Returns dict with step info."""
    persona = load_persona()
    if persona['first_run_complete']:
        return {
            'is_first_run': False,
            'user_name': persona['user_name'],
            'agent_name': persona['investigator_name'],
        }
    return {
        'is_first_run': True,
        'steps': ONBOARDING_STEPS,
        'user_name': persona.get('user_name', ''),
        'agent_name': persona.get('investigator_name', ''),
    }


def process_onboarding_step(step_id, user_input):
    """Process a user's response to an onboarding step.
    Returns (next_step_data, is_complete).
    """
    persona = load_persona()

    if step_id == 'ask_user_name':
        user_name = user_input.strip()
        if not user_name:
            return {'error': 'Please enter a name'}, False

        # Save immediately so it persists
        save_persona(persona.get('investigator_name', ''), user_name)

        # Prepare next step
        next_step = ONBOARDING_STEPS[2].copy()  # ask_agent_name
        next_step['agent_text'] = next_step['agent_text'].replace('{user_name}', user_name)
        return {'step': next_step, 'user_name': user_name}, False

    elif step_id == 'ask_agent_name':
        agent_name = user_input.strip()
        if not agent_name:
            return {'error': 'Please enter a name for your investigator'}, False

        user_name = persona.get('user_name', 'User')
        save_persona(agent_name, user_name)

        # Prepare confirm step
        next_step = ONBOARDING_STEPS[3].copy()
        next_step['agent_text'] = next_step['agent_text'].replace('{user_name}', user_name).replace('{agent_name}', agent_name)
        return {'step': next_step, 'agent_name': agent_name, 'user_name': user_name}, True

    return {'error': f'Unknown step: {step_id}'}, False


def get_greeting():
    """Get the returning user greeting message."""
    persona = load_persona()
    agent_name = persona.get('investigator_name', 'Investigator')
    user_name = persona.get('user_name', 'there')

    # Check if there are existing investigations
    from server.routes.investigation import list_investigations
    invs = list_investigations()
    active = [i for i in invs if i.get('active')]
    total = len(invs)

    # Filter out the blank placeholder investigation
    real_invs = [i for i in invs if i.get('name') != 'New Investigation']
    real_active = [i for i in active if i.get('name') != 'New Investigation']
    real_total = len(real_invs)

    if real_active:
        a = real_active[0]
        return {
            'agent_name': agent_name,
            'user_name': user_name,
            'greeting': f"Welcome back, {user_name}. Your current case is **{a['name']}** — {a['entities']} entities, {a['connections']} connections.\n\nWhat do you want to do?\n\n1. **Continue** this investigation\n2. **New investigation** — start a fresh case\n3. **Switch** to a different case ({real_total} saved)",
        }
    elif real_total > 0:
        return {
            'agent_name': agent_name,
            'user_name': user_name,
            'greeting': f"Welcome back, {user_name}. You have **{real_total}** saved investigations.\n\n1. **New investigation** — start a fresh case\n2. **Switch** to a previous case",
        }
    else:
        return {
            'agent_name': agent_name,
            'user_name': user_name,
            'greeting': f"Hey {user_name}, it's {agent_name}. What do you want to investigate today?",
        }
