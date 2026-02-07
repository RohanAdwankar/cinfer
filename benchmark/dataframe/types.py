from dataclasses import dataclass


@dataclass
class Scenario:
    name: str
    user_message: str
    expected_column: str
    column_exists: bool
