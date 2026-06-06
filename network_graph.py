import matplotlib.pyplot as plt
import networkx as nx


class IoTNetworkGraph:
    def __init__(self, registry):
        self.registry = registry
        self.graph = nx.DiGraph()
        self._build_graph()

    def _build_graph(self):
        self.graph.add_node("hivemq_broker", node_type="broker", label="HiveMQ\nBroker")

        for device_id, device in self.registry.devices.items():
            label = f"{device_id}\n({device.location})"
            self.graph.add_node(device_id, node_type=device.device_type, label=label)
            self.graph.add_edge(device_id, "hivemq_broker")
            self.graph.add_edge("hivemq_broker", device_id)

    def _compute_layout(self):
        positions = {}
        positions["hivemq_broker"] = (0.0, 0.0)

        esp32_nodes = [d for d, attrs in self.graph.nodes(data=True) if attrs.get("node_type") == "ESP32"]
        m3_nodes = [d for d, attrs in self.graph.nodes(data=True) if attrs.get("node_type") == "M3_Node"]

        for i, node_id in enumerate(esp32_nodes):
            y = (len(esp32_nodes) - 1) / 2 - i
            positions[node_id] = (-2.0, y)

        for i, node_id in enumerate(m3_nodes):
            y = (len(m3_nodes) - 1) / 2 - i
            positions[node_id] = (2.0, y)

        return positions

    def visualize(self, output_path="network_topology.png"):
        positions = self._compute_layout()
        fig, ax = plt.subplots(figsize=(14, 8))

        color_map = {"ESP32": "#4CAF50", "M3_Node": "#2196F3", "broker": "#F44336"}
        node_colors = [color_map.get(self.graph.nodes[n].get("node_type"), "#9E9E9E") for n in self.graph.nodes]
        node_sizes = [3500 if self.graph.nodes[n].get("node_type") == "broker" else 2500 for n in self.graph.nodes]

        nx.draw_networkx_edges(
            self.graph, positions, ax=ax,
            edge_color="#888888", arrows=True, arrowsize=15,
            connectionstyle="arc3,rad=0.1", width=1.2,
        )
        nx.draw_networkx_nodes(
            self.graph, positions, ax=ax,
            node_color=node_colors, node_size=node_sizes,
            edgecolors="black", linewidths=1.5,
        )

        labels = {n: self.graph.nodes[n].get("label", n) for n in self.graph.nodes}
        nx.draw_networkx_labels(self.graph, positions, labels=labels, ax=ax, font_size=8, font_weight="bold")

        legend_elements = [
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#4CAF50", markersize=12, label="ESP32"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#2196F3", markersize=12, label="M3 Node"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#F44336", markersize=12, label="Broker"),
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=10)

        ax.set_title("IoT Network Topology", fontsize=14, fontweight="bold")
        ax.axis("off")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()


if __name__ == "__main__":
    from device_registry import DeviceRegistry

    registry = DeviceRegistry()
    network = IoTNetworkGraph(registry)
    network.visualize("network_topology.png")

    print(f"Nodes: {len(network.graph.nodes())}")
    print(f"Edges: {len(network.graph.edges())}")
    print("Graph saved to network_topology.png")
