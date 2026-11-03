/* Words and options shown in the interface. Change anything here to make Jot yours. */
const CONFIG = {
  appName: 'Jot',
  tabs: [['home', 'Home'], ['map', 'Map'], ['timeline', 'Timeline'], ['stickers', 'Stickers'], ['settings', 'Settings']],
  labels: {
    jotButton: 'Jot It Down',
    updateTitle: 'Give an Update',
    updateHint: 'Tried one of your ideas? Close the loop and record how it went.',
    brainstormAI: 'Brainstorm with an LLM',
    brainstormOffline: 'Brainstorm (guided prompts)',
    groupWord: 'Groups',
  },
  /* How an idea ended up. `glyph` is drawn on the map. */
  statuses: {
    open:    { label: 'Open',          glyph: '●', help: 'Not tried yet' },
    worked:  { label: 'Worked',        glyph: '✔', help: 'Tried and it worked' },
    partial: { label: 'Partly worked', glyph: '◐', help: 'Mixed results' },
    failed:  { label: "Didn't work",   glyph: '✖', help: 'Tried, did not work' },
    shelved: { label: 'Parked',        glyph: '⏸', help: 'Set aside for now' },
  },
  eventTypes: {
    jot:        ['✏️', 'Jotted'],
    note:       ['📝', 'Wrote notes on'],
    brainstorm: ['💡', 'Brainstormed'],
    update:     ['✅', 'Gave an update on'],
    link:       ['🔗', 'Connected'],
    attach:     ['📎', 'Attached a file to'],
    sticker:    ['⭐', 'Minted a sticker'],
  },
  palettes: [
    ['ocean', 'Ocean', '#3a6ff0'], ['forest', 'Forest', '#2a8a5a'], ['sunset', 'Sunset', '#e0662a'],
    ['grape', 'Grape', '#8a4fd6'], ['rose', 'Rose', '#d63f78'], ['mono', 'Mono', '#3b3f4d'],
  ],
  groupColors: ['#4f8cff', '#f0873c', '#2fb87a', '#b36bf0', '#e5527a', '#d9b92e', '#2fb8c4', '#8b8f9a'],
  staleDays: 14, /* "still open" nudge on Home */
};
