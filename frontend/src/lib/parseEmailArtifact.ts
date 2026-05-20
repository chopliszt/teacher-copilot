/**
 * Parse the content of a ```email fenced code block that Marimba emits.
 *
 * Expected shape:
 *
 *   To: someone@example.com
 *   Subject: <one line>
 *   Body:
 *   <multi-line body>
 *
 * Tolerant of whitespace and case. Returns null if the structure is missing
 * its core markers — callers fall back to rendering the block as plain text
 * so the user never sees a broken composer.
 */
export interface ParsedEmailArtifact {
  to: string;
  subject: string;
  body: string;
}

export function parseEmailArtifact(content: string): ParsedEmailArtifact | null {
  const lines = content.split('\n');
  let to = '';
  let subject = '';
  let bodyStart = -1;
  let sawTo = false;
  let sawSubject = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!sawTo && /^\s*to\s*:/i.test(line)) {
      to = line.replace(/^\s*to\s*:\s*/i, '').trim();
      sawTo = true;
      continue;
    }
    if (!sawSubject && /^\s*subject\s*:/i.test(line)) {
      subject = line.replace(/^\s*subject\s*:\s*/i, '').trim();
      sawSubject = true;
      continue;
    }
    if (/^\s*body\s*:\s*$/i.test(line)) {
      bodyStart = i + 1;
      break;
    }
    // Single-line "Body: foo" — rare but handle it
    if (/^\s*body\s*:/i.test(line)) {
      const inline = line.replace(/^\s*body\s*:\s*/i, '');
      const rest = lines.slice(i + 1).join('\n');
      return {
        to,
        subject,
        body: (inline + (rest ? '\n' + rest : '')).trim(),
      };
    }
  }

  if (bodyStart < 0) {
    // No "Body:" marker — only treat it as an email artifact if we at least
    // got To: or Subject:, otherwise return null to fall back to plain code.
    if (!sawTo && !sawSubject) return null;
    return { to, subject, body: '' };
  }

  const body = lines.slice(bodyStart).join('\n').trim();
  return { to, subject, body };
}
