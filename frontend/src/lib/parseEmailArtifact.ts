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
        body: stripEmailMarkdown((inline + (rest ? '\n' + rest : '')).trim()),
      };
    }
  }

  if (bodyStart < 0) {
    // No "Body:" marker — only treat it as an email artifact if we at least
    // got To: or Subject:, otherwise return null to fall back to plain code.
    if (!sawTo && !sawSubject) return null;
    return { to, subject, body: '' };
  }

  const body = stripEmailMarkdown(lines.slice(bodyStart).join('\n').trim());
  return { to, subject, body };
}

/**
 * Strip markdown syntax that Marimba sometimes leaks into email bodies.
 * Real email clients render `**bold**` and `### header` literally, which
 * looks unprofessional. We run a conservative pass over the body before
 * it lands in the composer so the teacher never has to clean it up by hand.
 *
 * Conservative on purpose — we only touch patterns that are clearly
 * markdown noise (bold, headers, horizontal rules, fenced/inline code).
 * Asterisk bullets are converted to dashes; existing dash bullets stay.
 */
export function stripEmailMarkdown(text: string): string {
  return text
    // Horizontal rules: --- or *** or ___ alone on a line → blank line
    .replace(/^[ \t]*([-*_])[ \t]*\1[ \t]*\1[-*_ \t]*$/gm, '')
    // Headers: # Text, ## Text, … → Text
    .replace(/^[ \t]*#{1,6}[ \t]+(.*)$/gm, '$1')
    // Blockquotes: > text → text
    .replace(/^[ \t]*>[ \t]?/gm, '')
    // Bold: **text** → text  (run twice in case of nesting weirdness)
    .replace(/\*\*([^*\n]+?)\*\*/g, '$1')
    .replace(/\*\*([^*\n]+?)\*\*/g, '$1')
    // Bold alt: __text__ → text
    .replace(/__([^_\n]+?)__/g, '$1')
    // Inline code: `code` → code
    .replace(/`([^`\n]+?)`/g, '$1')
    // Asterisk bullets at line start → dash bullets
    .replace(/^([ \t]*)\*[ \t]+/gm, '$1- ')
    // Collapse 3+ consecutive blank lines into 2
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
