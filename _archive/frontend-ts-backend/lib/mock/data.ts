import type { Assessment, Conversation } from "@/types/health";

/*
 * SAMPLE DATA for UI preview only (see lib/preview.ts).
 * The medical wording is illustrative and has NOT been clinically reviewed.
 * It will be replaced by real data from the backend.
 */

export const mockUser = {
  id: "u_demo",
  name: "Asha Rao",
  email: "asha@example.com",
  role: "user" as const,
  memberSince: "2026-10-02T10:00:00.000Z",
};

export const mockConversations: Conversation[] = [
  {
    id: "c_headache",
    title: "Headache for two days",
    status: "completed",
    createdAt: "2026-11-16T08:12:00.000Z",
    updatedAt: "2026-11-16T08:24:00.000Z",
    assessmentId: "a_headache",
    messages: [
      {
        id: "m1",
        role: "user",
        content: "I've had a headache since yesterday morning.",
        createdAt: "2026-11-16T08:12:00.000Z",
      },
      {
        id: "m2",
        role: "assistant",
        content:
          "I'm sorry you're dealing with that. Before anything else: is this the worst headache you've ever had, or did it start suddenly like a thunderclap?",
        createdAt: "2026-11-16T08:12:20.000Z",
      },
      { id: "m3", role: "user", content: "No, it came on slowly.", createdAt: "2026-11-16T08:13:05.000Z" },
      {
        id: "m4",
        role: "assistant",
        content: "Thanks. On a scale of 1 to 10, how strong is the pain right now?",
        createdAt: "2026-11-16T08:13:20.000Z",
      },
      {
        id: "m5",
        role: "user",
        content: "About a 5. It gets worse when I look at my laptop screen.",
        createdAt: "2026-11-16T08:14:10.000Z",
      },
      {
        id: "m6",
        role: "assistant",
        content: "Have you had any fever, stiff neck, vomiting, confusion, or changes in your vision?",
        createdAt: "2026-11-16T08:14:25.000Z",
      },
      {
        id: "m7",
        role: "user",
        content: "No fever or anything like that. I have been sleeping badly this week though.",
        createdAt: "2026-11-16T08:15:40.000Z",
      },
      {
        id: "m8",
        role: "assistant",
        content:
          "Thank you, that's helpful. I have enough information to put together your health information report. Remember, this isn't a diagnosis. Your report is ready below.",
        createdAt: "2026-11-16T08:16:00.000Z",
      },
    ],
  },
  {
    id: "c_cough",
    title: "Dry cough and sore throat",
    status: "in_progress",
    createdAt: "2026-11-17T18:40:00.000Z",
    updatedAt: "2026-11-17T18:44:00.000Z",
    messages: [
      { id: "m1", role: "user", content: "I have a dry cough and a sore throat.", createdAt: "2026-11-17T18:40:00.000Z" },
      {
        id: "m2",
        role: "assistant",
        content:
          "I'm sorry to hear that. Are you having any trouble breathing, chest pain, or are your lips or face turning blue?",
        createdAt: "2026-11-17T18:40:15.000Z",
      },
      { id: "m3", role: "user", content: "No, nothing like that.", createdAt: "2026-11-17T18:41:30.000Z" },
      {
        id: "m4",
        role: "assistant",
        content: "Good to know. How many days have you had the cough?",
        createdAt: "2026-11-17T18:41:45.000Z",
      },
    ],
  },
  {
    id: "c_stomach",
    title: "Stomach pain after meals",
    status: "completed",
    createdAt: "2026-11-09T13:05:00.000Z",
    updatedAt: "2026-11-09T13:20:00.000Z",
    assessmentId: "a_stomach",
    messages: [
      {
        id: "m1",
        role: "user",
        content: "I get a burning stomach pain after I eat.",
        createdAt: "2026-11-09T13:05:00.000Z",
      },
      {
        id: "m2",
        role: "assistant",
        content: "I'm sorry you're uncomfortable. Have you vomited blood or noticed black, tarry stools?",
        createdAt: "2026-11-09T13:05:20.000Z",
      },
      { id: "m3", role: "user", content: "No.", createdAt: "2026-11-09T13:06:00.000Z" },
    ],
  },
  {
    id: "c_chest",
    title: "Chest pain while walking",
    status: "emergency_flagged",
    createdAt: "2026-10-28T21:15:00.000Z",
    updatedAt: "2026-10-28T21:16:00.000Z",
    assessmentId: "a_chest",
    messages: [
      {
        id: "m1",
        role: "user",
        content: "I have a tight pain in my chest and my left arm feels heavy.",
        createdAt: "2026-10-28T21:15:00.000Z",
      },
      {
        id: "m2",
        role: "assistant",
        content:
          "Chest tightness with arm heaviness can be a sign of a heart problem that needs emergency care. Please call your local emergency number or go to the nearest emergency department now. Don't drive yourself. If you are with someone, tell them now.",
        createdAt: "2026-10-28T21:15:05.000Z",
      },
    ],
  },
  {
    id: "c_tired",
    title: "Feeling tired all the time",
    status: "completed",
    createdAt: "2026-10-20T09:30:00.000Z",
    updatedAt: "2026-10-20T09:48:00.000Z",
    assessmentId: "a_tired",
    messages: [
      { id: "m1", role: "user", content: "I have been feeling tired for weeks.", createdAt: "2026-10-20T09:30:00.000Z" },
    ],
  },
];

export const mockAssessments: Assessment[] = [
  {
    id: "a_headache",
    conversationId: "c_headache",
    createdAt: "2026-11-16T08:16:00.000Z",
    symptoms: ["Headache", "Worse with screen use"],
    duration: "About 1 day (started yesterday morning)",
    severity: "Moderate, 5 out of 10",
    additionalInfo: [
      "Came on gradually, not suddenly",
      "No fever, stiff neck, vomiting, confusion or vision changes reported",
      "Poor sleep over the past week",
    ],
    possibleExplanations: [
      {
        name: "Tension-type headache",
        why: "Gradual onset, moderate pain, and recent poor sleep are commonly associated with tension-type headaches.",
      },
      {
        name: "Eye strain",
        why: "Pain that worsens with screen use can be linked to eye strain.",
      },
    ],
    warningSigns: [
      "A sudden, severe headache (the worst you've ever had)",
      "Fever with a stiff neck, or a rash",
      "Confusion, weakness, numbness, trouble speaking, or vision loss",
      "Headache after a head injury",
      "Headache that keeps getting worse over several days",
    ],
    nextSteps: [
      "Rest, stay hydrated, and take regular breaks from screens",
      "Keep a note of when the headache gets better or worse",
      "See a doctor if it lasts more than a few days or keeps coming back",
      "Ask a pharmacist or doctor before taking any medicine",
    ],
    urgencyLevel: "self_monitoring",
    urgencyReason: "No warning signs were reported. Monitor your symptoms and seek care if they change.",
  },
  {
    id: "a_stomach",
    conversationId: "c_stomach",
    createdAt: "2026-11-09T13:20:00.000Z",
    symptoms: ["Burning stomach pain", "Pain after meals"],
    duration: "About 2 weeks",
    severity: "Mild to moderate",
    additionalInfo: ["No vomiting of blood or black stools reported"],
    possibleExplanations: [
      { name: "Acid reflux or gastritis", why: "Burning pain after eating is often associated with stomach acid irritation." },
      { name: "Indigestion", why: "Discomfort linked to meals can come from indigestion." },
    ],
    warningSigns: [
      "Vomiting blood or material that looks like coffee grounds",
      "Black, tarry stools",
      "Severe pain that doesn't go away",
      "Unexplained weight loss or difficulty swallowing",
    ],
    nextSteps: [
      "Book an appointment with a doctor to discuss these symptoms",
      "Note which foods or times of day make it worse",
    ],
    urgencyLevel: "consultation",
    urgencyReason: "Symptoms lasting two weeks are worth discussing with a doctor.",
  },
  {
    id: "a_chest",
    conversationId: "c_chest",
    createdAt: "2026-10-28T21:15:05.000Z",
    symptoms: ["Chest tightness", "Heaviness in left arm"],
    duration: "Started minutes ago",
    severity: "Not assessed: emergency guidance given immediately",
    additionalInfo: [],
    possibleExplanations: [],
    warningSigns: ["Chest pain or tightness with arm, jaw or back pain is an emergency warning sign"],
    nextSteps: [
      "Call your local emergency number or go to the nearest emergency department now",
      "Do not drive yourself",
    ],
    urgencyLevel: "emergency",
    urgencyReason: "Chest tightness with arm heaviness can signal a heart attack.",
  },
  {
    id: "a_tired",
    conversationId: "c_tired",
    createdAt: "2026-10-20T09:48:00.000Z",
    symptoms: ["Tiredness"],
    duration: "Several weeks",
    severity: "Moderate, affecting daily activities",
    additionalInfo: ["No weight loss reported"],
    possibleExplanations: [
      { name: "Poor sleep or stress", why: "Ongoing tiredness is often related to sleep or stress." },
      { name: "Low iron (anaemia)", why: "Tiredness over weeks can sometimes be linked to low iron levels." },
    ],
    warningSigns: ["Shortness of breath at rest", "Fainting", "Unexplained weight loss or night sweats"],
    nextSteps: ["See a doctor, who may suggest a blood test", "Track your sleep and energy over the next week"],
    urgencyLevel: "consultation",
    urgencyReason: "Tiredness lasting several weeks should be checked by a doctor.",
  },
];

export function getMockConversation(id: string) {
  return mockConversations.find((c) => c.id === id);
}

export function getMockAssessment(id: string) {
  return mockAssessments.find((a) => a.id === id);
}
