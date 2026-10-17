
"use client";

import { useCallback, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  addEdge,
  useNodesState,
  useEdgesState,
  type Node,
  type NodeProps,
  type Edge,
  type Connection,
  type NodeTypes,
} from "@xyflow/react";
import {
  Plus,
  Play,
  Save,
  Zap,
  Bot,
  GitBranch,
  Mail,
  Clock3,
  LayoutDashboard,
  Workflow,
  History,
  Settings,
  Search,
  Bell,
  ChevronDown,
  Sparkles,
  PanelLeftClose,
  CircleHelp,
} from "lucide-react";

type WorkflowData = {
  label: string;
  subtitle: string;
  icon: string;
  accent: string;
};

type WorkflowNode = Node<WorkflowData, "workflow">;

function CustomNode({ data, selected }: NodeProps<WorkflowNode>) {
  const icons: Record<string, typeof Zap> = {
    trigger: Zap,
    ai: Bot,
    condition: GitBranch,
    email: Mail,
    delay: Clock3,
  };

  const Icon = icons[data.icon] || Zap;

  return (
    <div className={`workflow-node ${selected ? "node-selected" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div
        className="node-icon"
        style={{ background: `${data.accent}20`, color: data.accent }}
      >
        <Icon size={18} />
      </div>
      <div className="node-copy">
        <span className="node-subtitle">{data.subtitle}</span>
        <strong>{data.label}</strong>
      </div>
      <span className="node-status" />
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  workflow: CustomNode,
};

const initialNodes: WorkflowNode[] = [
  {
    id: "trigger-1",
    type: "workflow",
    position: { x: 80, y: 180 },
    data: {
      label: "New Website Lead",
      subtitle: "TRIGGER",
      icon: "trigger",
      accent: "#9B826D",
    },
  },
  {
    id: "ai-1",
    type: "workflow",
    position: { x: 370, y: 180 },
    data: {
      label: "Score Lead",
      subtitle: "AI PROCESSING",
      icon: "ai",
      accent: "#A77959",
    },
  },
  {
    id: "condition-1",
    type: "workflow",
    position: { x: 660, y: 180 },
    data: {
      label: "Check Lead Score",
      subtitle: "CONDITION",
      icon: "condition",
      accent: "#B58D5F",
    },
  },
  {
    id: "email-1",
    type: "workflow",
    position: { x: 960, y: 80 },
    data: {
      label: "Send Sales Email",
      subtitle: "ACTION",
      icon: "email",
      accent: "#718B70",
    },
  },
];

const initialEdges: Edge[] = [
  { id: "e1", source: "trigger-1", target: "ai-1", animated: true },
  { id: "e2", source: "ai-1", target: "condition-1", animated: true },
  {
    id: "e3",
    source: "condition-1",
    target: "email-1",
    label: "Yes",
    animated: true,
  },
];

const palette = [
  { label: "Trigger", subtitle: "Start a workflow", icon: "trigger", accent: "#9B826D" },
  { label: "AI Processing", subtitle: "Use AI to decide", icon: "ai", accent: "#A77959" },
  { label: "Condition", subtitle: "Branch your flow", icon: "condition", accent: "#B58D5F" },
  { label: "Send Email", subtitle: "Email action", icon: "email", accent: "#718B70" },
  { label: "Delay", subtitle: "Wait before continuing", icon: "delay", accent: "#BD8966" },
];

export default function Home() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [workflowName, setWorkflowName] = useState("Lead Qualification");
  const [savedWorkflowId, setSavedWorkflowId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [running, setRunning] = useState(false);
  const [executionResult, setExecutionResult] = useState("");

  const onConnect = useCallback(
    (connection: Connection) =>
      setEdges((current) =>
        addEdge({ ...connection, animated: true }, current)
      ),
    [setEdges]
  );

  function addWorkflowNode(item: (typeof palette)[number]) {
    const id = `${item.icon}-${Date.now()}`;
    const newNode: WorkflowNode = {
      id,
      type: "workflow",
      position: { x: 180 + Math.random() * 180, y: 100 + Math.random() * 260 },
      data: {
        label: item.label === "AI Processing" ? "New AI Task" : item.label,
        subtitle: item.label.toUpperCase(),
        icon: item.icon,
        accent: item.accent,
      },
    };
    setNodes((current) => [...current, newNode]);
    setSelectedNode(id);
    setNotice(`${item.label} node added`);
    window.setTimeout(() => setNotice(""), 2200);
  }
  
async function saveDraft() {
  if (!workflowName.trim()) {
    setNotice("Please enter a workflow name.");
    return;
  }

  if (nodes.length === 0) {
    setNotice("Add at least one node before saving.");
    return;
  }

  setSaving(true);
  setNotice("Saving workflow to Nexora database...");

  try {
    const backendTypes: Record<string, string> = {
      trigger: "trigger",
      ai: "ai",
      condition: "condition",
      email: "action",
      delay: "action",
    };

    const workflowPayload = {
      name: workflowName.trim(),
      description: "Workflow created using Nexora visual builder.",
      nodes: nodes.map((node) => {
        const data = node.data as WorkflowData;

        return {
          id: node.id,
          type: backendTypes[data.icon] ?? "action",
          name: data.label,
          config:
            data.icon === "ai"
              ? {
                  task: "general",
                  instructions: "Process the incoming workflow data.",
                }
              : data.icon === "condition"
                ? {
                    field: "score",
                    operator: ">=",
                    value: 70,
                  }
                : data.icon === "email"
                  ? {
                      action_type: "email",
                    }
                  : data.icon === "delay"
                    ? {
                        action_type: "delay",
                        seconds: 5,
                      }
                    : {},
          retry_count: 0,
        };
      }),
      edges: edges.map((edge) => ({
        source: edge.source,
        target: edge.target,
        condition:
          typeof edge.label === "string" ? edge.label : null,
      })),
    };

    const response = await fetch("http://127.0.0.1:8000/workflows/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(workflowPayload),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail ?? data)
      );
    }

    setSavedWorkflowId(data.workflow_id);
    setNotice(`Workflow saved successfully! ID: ${data.workflow_id}`);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown error";

    setNotice(`Save failed: ${message}`);
  } finally {
    setSaving(false);
  }
}


  
async function runPreview() {
  setRunning(true);
  setExecutionResult("");
  setNotice("Sending workflow execution request to Nexora backend...");

  try {
    if (!savedWorkflowId) {
  setNotice("Please save your workflow before testing it.");
  return;
}

const workflowId = savedWorkflowId;
    const response = await fetch(
      `http://127.0.0.1:8000/workflows/${workflowId}/runs`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          input_data: {
            name: "Aarav Sharma",
            email: "aarav@example.com",
            company: "Acme Technologies",
            message:
              "We need an AI-powered sales automation solution. Please share pricing and a demo.",
          },
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail
          ? JSON.stringify(data.detail)
          : `Request failed with status ${response.status}`
      );
    }

    setExecutionResult(JSON.stringify(data, null, 2));
    setNotice("Backend execution request completed. Check the result below.");
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown error";

    setExecutionResult(`Error: ${message}`);
    setNotice("Workflow request failed. Check the result below.");
  } finally {
    setRunning(false);
  }
}

  const selected = nodes.find((node) => node.id === selectedNode);

  return (
    <main className="nexora-app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Workflow size={22} /></div>
          <span>NEXORA<span className="brand-dot">.</span></span>
          <button className="icon-button sidebar-collapse" aria-label="Collapse sidebar">
            <PanelLeftClose size={17} />
          </button>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <button className="workspace-switch">
          <div className="workspace-avatar">N</div>
          <div className="workspace-text">
            <strong>Nexora Labs</strong>
            <span>Free workspace</span>
          </div>
          <ChevronDown size={15} />
        </button>

        <div className="nav-section-label">BUILD</div>
        <nav className="sidebar-nav">
          <button className="nav-item"><LayoutDashboard size={18} /> Overview</button>
          <button className="nav-item active"><Workflow size={18} /> Workflows <span className="nav-count">4</span></button>
          <button className="nav-item"><History size={18} /> Execution history</button>
        </nav>

        <div className="nav-section-label">MANAGE</div>
        <nav className="sidebar-nav">
          <button className="nav-item"><Settings size={18} /> Settings</button>
          <button className="nav-item"><CircleHelp size={18} /> Help & support</button>
        </nav>

        <div className="sidebar-bottom">
          <div className="upgrade-card">
            <div className="upgrade-icon"><Sparkles size={18} /></div>
            <strong>Build something great</strong>
            <p>Your ideas, connected into workflows.</p>
            <span className="upgrade-tag">NEXORA STUDIO</span>
          </div>
          <div className="profile">
            <div className="profile-avatar">S</div>
            <div className="profile-text"><strong>Workspace owner</strong><span>Developer plan</span></div>
            <Settings size={16} />
          </div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workflows</span><span className="breadcrumb-slash">/</span>
            <strong>Editor</strong>
          </div>
          <div className="topbar-actions">
            <span className="saved-indicator"><span /> Draft workspace</span>
            <button className="icon-button" aria-label="Notifications"><Bell size={18} /></button>
            <div className="topbar-avatar">S</div>
          </div>
        </header>

        <div className="editor-heading">
          <div className="heading-left">
            <div className="eyebrow"><span className="eyebrow-dot" /> WORKFLOW EDITOR</div>
            <input
              className="workflow-title"
              value={workflowName}
              onChange={(event) => setWorkflowName(event.target.value)}
              aria-label="Workflow name"
            />
            <p>Design, connect, and automate your business processes.</p>
          </div>
          <div className="heading-actions">
            <button
  className="secondary-button"
  onClick={saveDraft}
  disabled={saving}
>
  <Save size={16} />
  {saving ? "Saving..." : "Save draft"}
</button>
            <button className="primary-button" onClick={runPreview} disabled={running}>
              <Play size={16} fill="currentColor" /> {running ? "Running..." : "Test workflow"}
            </button>
          </div>
        </div>

        <div className="stats-row">
          <div className="stat-card"><span className="stat-label">TOTAL NODES</span><strong>{nodes.length.toString().padStart(2, "0")}</strong><span className="stat-note">In this workflow</span></div>
          <div className="stat-card"><span className="stat-label">CONNECTIONS</span><strong>{edges.length.toString().padStart(2, "0")}</strong><span className="stat-note">Connected paths</span></div>
          <div className="stat-card"><span className="stat-label">WORKFLOW STATUS</span><strong className="status-draft">Draft</strong><span className="stat-note">Not published</span></div>
          <div className="stat-card ai-stat"><span className="stat-label">POWERED BY</span><strong><Sparkles size={17} /> Nexora AI</strong><span className="stat-note">Automation workspace</span></div>
        </div>

        <section className="builder-card">
          <div className="builder-toolbar">
            <div className="canvas-title"><span className="live-dot" /> Workflow canvas <span className="canvas-pill">VISUAL EDITOR</span></div>
            <div className="canvas-tools">
              <button className="toolbar-button" onClick={() => addWorkflowNode(palette[0])}><Plus size={15} /> Add node</button>
              <button className="toolbar-button" onClick={() => { setNodes(initialNodes); setEdges(initialEdges); setSelectedNode(null); }}>Reset canvas</button>
            </div>
          </div>

          <div className="canvas-layout">
            <div className="canvas-area">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onNodeClick={(_, node) => setSelectedNode(node.id)}
                onPaneClick={() => setSelectedNode(null)}
                fitView
                minZoom={0.25}
                maxZoom={1.5}
                proOptions={{ hideAttribution: true }}
              >
                <Background color="#D9C5B2" gap={22} size={1} />
                <Controls />
                <MiniMap
                  nodeColor={(node) => (node.data as WorkflowData).accent}
                  maskColor="rgba(247, 241, 233, 0.72)"
                />
              </ReactFlow>
              <div className="canvas-hint"><span>↖</span> Drag nodes · Connect handles · Scroll to zoom</div>
            </div>

            <aside className="node-panel">
              <div className="panel-heading">
                <div><span className="panel-kicker">TOOLKIT</span><h3>Add a node</h3></div>
                <Search size={17} />
              </div>
              <p className="panel-description">Choose a building block for your workflow.</p>
              <div className="palette-list">
                {palette.map((item) => {
                  const Icon = item.icon === "trigger" ? Zap : item.icon === "ai" ? Bot : item.icon === "condition" ? GitBranch : item.icon === "email" ? Mail : Clock3;
                  return (
                    <button className="palette-item" key={item.icon} onClick={() => addWorkflowNode(item)}>
                      <div className="palette-icon" style={{ color: item.accent, background: `${item.accent}18` }}><Icon size={18} /></div>
                      <div className="palette-copy"><strong>{item.label}</strong><span>{item.subtitle}</span></div>
                      <Plus size={16} className="palette-plus" />
                    </button>
                  );
                })}
              </div>

              <div className="panel-divider" />
              <div className="panel-heading property-heading">
                <div><span className="panel-kicker">PROPERTIES</span><h3>Selected node</h3></div>
              </div>
              {selected ? (
                <div className="selected-properties">
                  <label>Node name</label>
                  <input
                    value={(selected.data as WorkflowData).label}
                    onChange={(event) => setNodes((current) => current.map((node) => node.id === selected.id ? { ...node, data: { ...(node.data as WorkflowData), label: event.target.value } } : node))}
                  />
                  <span className="property-help">Select a node on the canvas to edit it.</span>
                  <button className="delete-node" onClick={() => { setNodes((current) => current.filter((node) => node.id !== selected.id)); setEdges((current) => current.filter((edge) => edge.source !== selected.id && edge.target !== selected.id)); setSelectedNode(null); }}>Remove node</button>
                </div>
              ) : (
                <p className="empty-properties">Select any node on the canvas to view and edit its properties.</p>
              )}
            </aside>
          </div>
        </section>
        
{executionResult && (
  <section className="execution-result">
    <div className="execution-result-heading">
      <strong>Execution response</strong>
      <button
        className="toolbar-button"
        onClick={() => setExecutionResult("")}
      >
        Clear result
      </button>
    </div>
    <pre>{executionResult}</pre>
  </section>
)}

        <footer className="footer-line"><span>© 2026 Nexora</span><span><span className="footer-status" /> All changes are local to this browser session</span></footer>
      </section>

      {notice && <div className="toast"><Sparkles size={16} /> {notice}</div>}
    </main>
  );
}
