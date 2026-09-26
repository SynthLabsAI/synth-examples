"""Original, redistributable DispatchDesk teaching cases, not historical PRs.

The public policy is the specification. Finite input domains are also supplied
to the actor without expected answers. Assessment labels stay private. Bug/clean
siblings stay in the same split. All monetary quantities are integer cents.
"""
from itertools import product


def grid(**fields):
    return [dict(zip(fields, values)) for values in product(*fields.values())]


CASES = [
    dict(name='exports', split='practice',
         policy='Only an administrator in the owning organization may download an export. Both conditions are required. Organization identifiers are opaque case-sensitive strings.',
         before='return x["admin"] and x["user_org"] == x["export_org"]',
         after='return x["admin"] or x["user_org"] == x["export_org"]',
         clean='return x["user_org"] == x["export_org"] and x["admin"]',
         domain=grid(admin=[False, True], user_org=['alpha', 'beta'], export_org=['alpha', 'beta']),
         root='The OR grants a non-admin access in their own organization and an admin access across organizations.'),
    dict(name='webhooks', split='practice',
         policy='A signed webhook is accepted only when its signature is valid and its age in seconds is between 0 and 300 inclusive. Future-dated events must be rejected, even with a valid signature. now and sent are integer UTC seconds.',
         before='return x["signature_valid"] and 0 <= x["now"] - x["sent"] <= 300',
         after='return x["signature_valid"] and abs(x["now"] - x["sent"]) <= 300',
         clean='age = x["now"] - x["sent"]\n    return bool(x["signature_valid"] and age >= 0 and age <= 300)',
         domain=grid(signature_valid=[False, True], now=[1000], sent=[699, 700, 999, 1000, 1001, 1300, 1301]),
         root='Using absolute age admits signed events dated in the future, contrary to the freshness policy.'),
    dict(name='invites', split='practice',
         policy='A new member invitation is allowed only when active members plus outstanding invitations is strictly less than the organization seat limit. Pending invitations reserve seats until accepted or revoked. Counts and limits are nonnegative integers.',
         before='return x["members"] + x["pending"] < x["limit"]',
         after='return x["members"] < x["limit"]',
         clean='reserved = x["members"] + x["pending"]\n    return reserved < x["limit"]',
         domain=grid(members=[0, 1, 3], pending=[0, 1, 3], limit=[0, 1, 3, 5]),
         root='Ignoring pending invitations allows more reserved seats than the organization bought.'),
    dict(name='quota', split='practice',
         policy='An upload may reserve storage only when committed bytes plus bytes reserved by concurrent uploads plus this upload size does not exceed the quota. Reservations are included to avoid oversubscription. Values are nonnegative integers.',
         before='return x["committed"] + x["reserved"] + x["size"] <= x["limit"]',
         after='return x["committed"] + x["size"] <= x["limit"]',
         clean='available = x["limit"] - x["committed"] - x["reserved"]\n    return x["size"] <= available',
         domain=grid(committed=[0, 10], reserved=[0, 5, 10], size=[0, 5, 10], limit=[10, 20]),
         root='Ignoring outstanding reservations oversubscribes storage when multiple uploads are in flight.'),
    dict(name='paths', split='held-out',
         policy='The report server accepts a normalized absolute POSIX path only if it equals /srv/reports or is below /srv/reports/. Inputs are already normalized, contain no symlinks, and have no trailing slash except the root. A similarly named sibling directory is not inside the root.',
         before='return x["path"] == "/srv/reports" or x["path"].startswith("/srv/reports/")',
         after='return x["path"].startswith("/srv/reports")',
         clean='root = "/srv/reports"\n    return x["path"] == root or x["path"].startswith(root + "/")',
         domain=grid(path=['/srv/reports', '/srv/reports/a.csv', '/srv/reports-other/a.csv', '/srv/reports2', '/srv/other']),
         root='A lexical prefix without the directory boundary accepts similarly named siblings outside the report root.'),
    dict(name='pagination', split='held-out',
         policy='A continuation cursor is the last item returned on the previous page. The next page returns sorted item identifiers strictly greater than that cursor, at most limit items. Input identifiers are unique positive integers; cursor is nonnegative and limit is a positive integer.',
         before='return sorted(i for i in x["items"] if i > x["cursor"])[:x["limit"]]',
         after='return sorted(i for i in x["items"] if i >= x["cursor"])[:x["limit"]]',
         clean='remaining = [i for i in sorted(x["items"]) if i > x["cursor"]]\n    return remaining[:x["limit"]]',
         domain=grid(items=[[], [1, 2, 3], [9, 2, 5]], cursor=[0, 1, 2, 5, 9], limit=[1, 2, 3]),
         root='Including the cursor repeats the last record and can prevent a page-size-one reader from advancing.'),
    dict(name='idempotency', split='held-out',
         policy='A delivery is a duplicate only if the same organization and event identifier pair was already seen. Event IDs are unique only inside an organization. seen is a list of [organization, event] pairs. All identifiers are opaque case-sensitive strings.',
         before='return [x["org"], x["event"]] in x["seen"]',
         after='return any(event == x["event"] for org, event in x["seen"])',
         clean='key = [x["org"], x["event"]]\n    return any(pair == key for pair in x["seen"])',
         domain=grid(org=['alpha', 'beta'], event=['e1', 'e2'], seen=[[], [['alpha', 'e1']], [['beta', 'e2']]]),
         root='Dropping organization from the deduplication key suppresses a legitimate delivery in another tenant.'),
    dict(name='retention', split='held-out',
         policy='An expired record may be deleted only after its expiration time and only if no legal hold applies. Exactly at expiration it is still retained. A legal hold has priority over expiration. now and expires are integer UTC seconds.',
         before='return x["now"] > x["expires"] and not x["legal_hold"]',
         after='return x["now"] > x["expires"] or not x["legal_hold"]',
         clean='expired = x["expires"] < x["now"]\n    return not x["legal_hold"] and expired',
         domain=grid(now=[99, 100, 101], expires=[100], legal_hold=[False, True]),
         root='The OR permits deletion before expiration without a hold, and of expired records even under legal hold.'),
]

# More involved review cases. The first collection above is retained as a
# foundation, not used to manufacture gradient updates after perfect scores.
FOUNDATION = CASES
for case in FOUNDATION:
    case['level'] = 'core' if case['split'] == 'held-out' else 'foundation'

CASES = FOUNDATION + [
    dict(name='apportionment', split='practice', level='core',
         policy='Allocate total integer cents across positive integer weights. Each recipient gets floor(total*weight/sum(weights)), then distribute remaining cents to the largest fractional remainders, breaking ties by earlier input index. Arithmetic must be exact for arbitrarily large nonnegative integer total and positive weights. Return allocations in original order.',
         before='from fractions import Fraction\n    weights = x["weights"]\n    shares = [Fraction(x["total"] * w, sum(weights)) for w in weights]\n    amounts = [int(s) for s in shares]\n    order = sorted(range(len(weights)), key=lambda i: (-(shares[i]-amounts[i]), i))\n    for i in order[:x["total"]-sum(amounts)]:\n        amounts[i] += 1\n    return amounts',
         after='weights = x["weights"]\n    shares = [x["total"] * w / sum(weights) for w in weights]\n    amounts = [int(s) for s in shares]\n    order = sorted(range(len(weights)), key=lambda i: (-(shares[i]-amounts[i]), i))\n    for i in order[:x["total"]-sum(amounts)]:\n        amounts[i] += 1\n    return amounts',
         clean='weights = x["weights"]\n    denominator = sum(weights)\n    parts = [divmod(x["total"] * w, denominator) for w in weights]\n    amounts = [p[0] for p in parts]\n    order = sorted(range(len(weights)), key=lambda i: (-parts[i][1], i))\n    for i in order[:x["total"]-sum(amounts)]:\n        amounts[i] += 1\n    return amounts',
         domain=grid(total=[0, 1, 100, 9007199254740993, 9007199254740995, 9007199254741001], weights=[[1,1],[1,2,3],[7,11,13]]),
         root='Binary floating-point division loses exact cents and remainders for large totals; allocations can differ from the exact largest-remainder rule or fail to sum to total.'),
    dict(name='rolecache', split='practice', level='core',
         policy='For each request [organization, role], return whether that exact pair is in allowed. Identifiers are opaque strings and may contain a colon. A cache may speed repeated lookups but must not change authorization. Decisions appear in request order.',
         before='cache = {}\n    result = []\n    for org, role in x["requests"]:\n        key = (org, role)\n        if key not in cache:\n            cache[key] = [org, role] in x["allowed"]\n        result.append(cache[key])\n    return result',
         after='cache = {}\n    result = []\n    for org, role in x["requests"]:\n        key = org + ":" + role\n        if key not in cache:\n            cache[key] = [org, role] in x["allowed"]\n        result.append(cache[key])\n    return result',
         clean='cache = {}\n    result = []\n    for pair in x["requests"]:\n        key = tuple(pair)\n        if key not in cache:\n            cache[key] = pair in x["allowed"]\n        result.append(cache[key])\n    return result',
         domain=[{'requests': [['a','admin'],['b','admin']], 'allowed': [['a','admin']]},
                 {'requests': [['a:b','c'],['a','b:c']], 'allowed': [['a:b','c']]},
                 {'requests': [['a','b:c'],['a:b','c']], 'allowed': [['a:b','c']]}],
         root='Delimiter concatenation collides across distinct organization-role pairs containing colons; the first cached authorization can be reused for another pair.'),
    dict(name='queuepages', split='practice', level='core',
         policy='A queue page contains up to limit visible records with increasing IDs greater than cursor. Hidden records do not consume page slots. There are unique IDs, positive limit, and rows are [id, visible]. Return IDs only.',
         before='eligible = sorted((r for r in x["rows"] if r[0] > x["cursor"] and r[1]), key=lambda r: r[0])\n    return [r[0] for r in eligible[:x["limit"]]]',
         after='eligible = sorted((r for r in x["rows"] if r[0] > x["cursor"]), key=lambda r: r[0])\n    return [r[0] for r in eligible[:x["limit"]] if r[1]]',
         clean='ordered = sorted(x["rows"], key=lambda r: r[0])\n    visible = [r[0] for r in ordered if r[0] > x["cursor"] and r[1]]\n    return visible[:x["limit"]]',
         domain=grid(rows=[[[1,False],[2,True],[3,True]], [[1,True],[2,False],[3,True]], []], cursor=[0,1], limit=[1,2]),
         root='Applying the page limit before visibility filtering lets hidden records consume slots; the page can be empty despite available visible work.'),
    dict(name='creditround', split='practice', level='core',
         policy='Each signed amount in integer millicents is posted separately to integer cents using nearest rounding, with exact halfway cases rounded away from zero. Return their sum. Never net amounts before rounding. Negative amounts are refunds and must obey the same symmetric rule.',
         before='def post(n):\n        return (1 if n >= 0 else -1) * ((abs(n) + 500) // 1000)\n    return sum(post(n) for n in x["amounts"])',
         after='def post(n):\n        return (n + 500) // 1000\n    return sum(post(n) for n in x["amounts"])',
         clean='def post(n):\n        q, r = divmod(abs(n), 1000)\n        return (q + int(r >= 500)) * (1 if n >= 0 else -1)\n    return sum(post(n) for n in x["amounts"])',
         domain=grid(amounts=[[], [500], [-500], [-1500], [499,-499], [1500,-1500], [501,-501], [499,499]]),
         root='The add-half floor formula rounds negative halfway refunds toward zero instead of away from zero, creating asymmetric postings.'),
    dict(name='snapshot', split='extension', level='extension',
         policy='For each [key, delta] operation update the integer counter for that key and append an independent snapshot of all current counters. Later updates must not change earlier snapshots. Initial state is empty. Return snapshots in order.',
         before='state = {}\n    snapshots = []\n    for key, delta in x["operations"]:\n        state[key] = state.get(key, 0) + delta\n        snapshots.append(dict(state))\n    return snapshots',
         after='state = {}\n    snapshots = []\n    for key, delta in x["operations"]:\n        state[key] = state.get(key, 0) + delta\n        snapshots.append(state)\n    return snapshots',
         clean='state = {}\n    snapshots = []\n    for key, delta in x["operations"]:\n        state = {**state, key: state.get(key, 0) + delta}\n        snapshots.append(state)\n    return snapshots',
         domain=grid(operations=[[], [['a',1]], [['a',1],['a',2]], [['a',1],['b',2]], [['a',1],['a',-1]]]),
         root='Appending the same mutable dictionary aliases all snapshots, so later counter updates rewrite earlier history.'),
    dict(name='mergeorder', split='extension', level='extension',
         policy='Rows are [timestamp, id]. Return IDs sorted by descending timestamp, keeping input order for equal timestamps. IDs are opaque and do not define priority. A refactor must preserve this stable ordering.',
         before='return [r[1] for r in sorted(x["rows"], key=lambda r: -r[0])]',
         after='return [r[1] for r in sorted(x["rows"], reverse=True)]',
         clean='return [r[1] for r in sorted(x["rows"], key=lambda r: r[0], reverse=True)]',
         domain=grid(rows=[[], [[1,'a'],[1,'b']], [[1,'b'],[1,'a']], [[2,'a'],[1,'c'],[2,'b']]]),
         root='Sorting entire rows makes ID a secondary reverse sort key, violating stable arrival order at equal timestamps.'),
    dict(name='retrywindow', split='extension', level='extension',
         policy='Count events with timestamps strictly after now-window and at or before now. Duplicate timestamps represent separate events. Input timestamps may be in any order. Return whether the count is less than limit. window and limit are positive integers.',
         before='recent = [t for t in x["events"] if x["now"]-x["window"] < t <= x["now"]]\n    return len(recent) < x["limit"]',
         after='recent = {t for t in x["events"] if x["now"]-x["window"] < t <= x["now"]}\n    return len(recent) < x["limit"]',
         clean='count = sum(1 for t in x["events"] if t <= x["now"] and t > x["now"]-x["window"])\n    return count < x["limit"]',
         domain=grid(events=[[],[99,99],[99,100],[90,99,99],[101,99,99]], now=[100], window=[10], limit=[1,2,3]),
         root='Converting timestamps to a set collapses simultaneous events and undercounts usage, admitting attempts above the intended rate limit.'),
    dict(name='endexclusive', split='extension', level='extension',
         policy='Booking intervals are half-open [start,end). Reject a proposed positive-duration interval if it overlaps an existing interval; touching endpoints are allowed. Existing intervals may overlap each other. Return whether the proposal is accepted.',
         before='return not any(x["start"] < end and start < x["end"] for start, end in x["bookings"])',
         after='return not any(x["start"] <= end and start <= x["end"] for start, end in x["bookings"])',
         clean='return all(end <= x["start"] or x["end"] <= start for start, end in x["bookings"])',
         domain=grid(start=[0,1,2], end=[3,4], bookings=[[],[[3,5]], [[-1,0]], [[1,2]], [[0,1],[3,4]]]),
         root='Inclusive overlap comparisons reject adjacent non-overlapping bookings that share an endpoint.'),
]


def source(body):
    return '"""DispatchDesk policy adapter; called by app.py."""\n\ndef decide(x):\n    ' + body + '\n'
