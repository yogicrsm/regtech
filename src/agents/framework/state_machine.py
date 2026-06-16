import json
import logging

class StateGraph:
    def __init__(self, initial_state: dict):
        self.state = initial_state
        self.nodes = {}
        self.edges = {}

    def add_node(self, name, func):
        self.nodes[name] = func

    def add_edge(self, start, end_func):
        self.edges[start] = end_func

    def run(self, start_node):
        current = start_node
        while current:
            logging.info(f"Transitioning to: {current}")
            self.state = self.nodes[current](self.state)
            # The edge function determines the next node
            current = self.edges[current](self.state)
        return self.state