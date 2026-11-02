import re


def segment_clauses(text: str):
    """
    Segment a legal document into numbered clauses.

    Supports patterns such as:

        1. Definitions
        2. Termination
        3. Confidentiality

    and also:

        1. Term. The agreement...
        2. Termination. Either party...

    The first sentence/heading becomes the clause title,
    while the remaining text becomes the clause body.
    """

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # A clause begins at a numbered heading.
    #
    # Examples:
    # 1. Term
    # 2. Termination
    # 10. Confidentiality
    #
    # We deliberately require the number to appear at the
    # beginning of a line.
    heading_pattern = re.compile(
        r"(?m)^\s*(\d+)\.\s+(.+?)\s*$"
    )

    matches = list(
        heading_pattern.finditer(text)
    )

    clauses = []

    for i, match in enumerate(matches):

        clause_number = int(
            match.group(1)
        )

        heading_line = match.group(2).strip()

        body_start = match.end()

        if i + 1 < len(matches):
            body_end = matches[i + 1].start()
        else:
            body_end = len(text)

        remaining_body = text[
            body_start:body_end
        ].strip()

        # -------------------------------------------------
        # Handle cases such as:
        #
        # 2. Term. The term of this Agreement...
        #
        # The PDF extractor may put the heading and body
        # on the same line.
        # -------------------------------------------------

        title = heading_line
        body = remaining_body

        # If the extracted heading itself contains a full
        # sentence, split at the first sentence boundary.
        sentence_match = re.match(
            r"^(.+?\.)\s+(.+)$",
            heading_line
        )

        if sentence_match:

            possible_title = (
                sentence_match.group(1).strip()
            )

            possible_body = (
                sentence_match.group(2).strip()
            )

            # Use the first sentence as the title only
            # when it looks like a normal short heading.
            if (
                len(possible_title) <= 100
                and len(possible_body) >= 10
            ):
                title = possible_title.rstrip(".")

                body_parts = [
                    possible_body
                ]

                if body:
                    body_parts.append(body)

                body = "\n".join(
                    body_parts
                )

        # -------------------------------------------------
        # Clean title
        # -------------------------------------------------

        title = re.sub(
            r"\s+",
            " ",
            title
        ).strip()

        title = title.rstrip(".")

        # -------------------------------------------------
        # Clean body
        # -------------------------------------------------

        body = re.sub(
            r"\n{3,}",
            "\n\n",
            body
        ).strip()

        clauses.append({

            "clause_id":
                clause_number,

            "title":
                title,

            "text":
                body
        })

    return clauses