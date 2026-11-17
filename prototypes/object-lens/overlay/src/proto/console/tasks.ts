// The hallway test's tasks: 5 questions, asked once about set A's object and once about set B's,
// each set in a different condition, so no analyst answers the same question twice. The answer
// key comes from the same synthetic world the pages show.
import { NOW, TARGETS, notsoOf, type Target } from "../data";
import { stampUtc } from "../../utils/ops";

export type Condition = "today" | "lens";
export type SetName = "A" | "B";

export interface Task {
  n: number;
  question: string;
  key: string;
}

const CHANNEL_NAMES: Record<string, string> = {
  "ch-ops": "SDA watch floor",
  "ch-geo": "GEO cell",
  "ch-leo": "LEO cell",
  "ch-coord": "Partner coordination",
};

const hoursFrom = (t: number) => {
  const h = (t - NOW) / 3_600_000;
  return h >= 0 ? `in about ${h.toFixed(1)} h (${stampUtc(t)})` : `about ${(-h).toFixed(1)} h ago (${stampUtc(t)})`;
};

function tasksFor(t: Target): Task[] {
  const obj = `${t.sat.name} (${t.sat.id})`;
  const latest = [...t.maneuvers].sort((a, b) => b.at - a.at)[0];
  return [
    { n: 1, question: `What is the next timer due on ${obj}, and roughly when?`, key: `"${t.timer.label}", ${hoursFrom(t.timer.at)}.` },
    { n: 2, question: `Which provider reported ${obj}'s most recent manoeuvre, and roughly when?`, key: `${latest.source}, ${hoursFrom(latest.at)}.` },
    {
      n: 3,
      question: `Someone on the floor raised a concern about ${obj}. Who, and in which channel?`,
      key: `${t.concern.author} in #${CHANNEL_NAMES[t.concern.channel]}; answered by ${t.reply.author}.`,
    },
    { n: 4, question: `What is the NOTSO number of ${obj}'s open notice, and what urgency did the assistant give it?`, key: `${notsoOf(t)}, HIGH.` },
    { n: 5, question: `What does the latest analyst note on ${obj} say needs doing?`, key: `"${t.note.text}" (${t.note.author}).` },
  ];
}

export const TASKS: Record<SetName, Task[]> = {
  A: tasksFor(TARGETS[0]),
  B: tasksFor(TARGETS[1]),
};

export const CONDITION_LABEL: Record<Condition, string> = {
  today: "Today's Holly",
  lens: "With the Object Lens",
};
