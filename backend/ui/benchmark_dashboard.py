#!/usr/bin/env python3
"""
Benchmark Analysis Dashboard

Streamlit-based interactive dashboard for analyzing Image-Toolkit benchmark results.
"""

import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


# Page configuration
st.set_page_config(
    page_title="Image-Toolkit Benchmark Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


class BenchmarkAnalyzer:
    """Analyzes and visualizes benchmark results."""

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.reports: List[Dict[str, Any]] = []
        self.load_reports()

    def load_reports(self):
        """Load all JSON benchmark reports from the results directory."""
        if not self.results_dir.exists():
            st.error(f"Results directory not found: {self.results_dir}")
            return

        json_files = sorted(self.results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

        for file_path in json_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    # Add file metadata
                    data['_file_path'] = str(file_path)
                    data['_file_name'] = file_path.name
                    self.reports.append(data)
            except (json.JSONDecodeError, KeyError) as e:
                st.warning(f"Failed to load {file_path.name}: {e}")

    def get_suite_names(self) -> List[str]:
        """Get unique suite names from loaded reports."""
        suites = set()
        for report in self.reports:
            if 'metadata' in report:
                suites.add(report['metadata']['suite_name'])
            elif 'suite' in report:
                suites.add(report['suite'])
        return sorted(list(suites))

    def get_reports_by_suite(self, suite_name: str) -> List[Dict[str, Any]]:
        """Get all reports for a specific suite."""
        return [
            r for r in self.reports
            if r.get('metadata', {}).get('suite_name') == suite_name
            or r.get('suite') == suite_name
        ]

    def create_time_comparison_chart(self, benchmarks: List[Dict[str, Any]], title: str):
        """Create a bar chart comparing execution times."""
        names = [b['name'] for b in benchmarks]
        avg_times = [b['time']['avg_sec'] for b in benchmarks]
        min_times = [b['time']['min_sec'] for b in benchmarks]
        max_times = [b['time']['max_sec'] for b in benchmarks]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Average Time',
            x=names,
            y=avg_times,
            error_y=dict(
                type='data',
                symmetric=False,
                array=[max_times[i] - avg_times[i] for i in range(len(avg_times))],
                arrayminus=[avg_times[i] - min_times[i] for i in range(len(avg_times))],
            ),
            marker_color='#4CAF50',
        ))

        fig.update_layout(
            title=title,
            xaxis_title="Benchmark",
            yaxis_title="Time (seconds)",
            template="plotly_white",
            height=500,
            xaxis={'tickangle': -45},
        )
        return fig

    def create_memory_comparison_chart(self, benchmarks: List[Dict[str, Any]], title: str):
        """Create a bar chart comparing memory usage."""
        names = [b['name'] for b in benchmarks]
        avg_mem = [b['memory']['avg_peak_mb'] for b in benchmarks]
        max_mem = [b['memory']['max_peak_mb'] for b in benchmarks]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Average Peak Memory',
            x=names,
            y=avg_mem,
            marker_color='#2196F3',
        ))
        fig.add_trace(go.Bar(
            name='Max Peak Memory',
            x=names,
            y=max_mem,
            marker_color='#FF9800',
        ))

        fig.update_layout(
            title=title,
            xaxis_title="Benchmark",
            yaxis_title="Memory (MB)",
            template="plotly_white",
            height=500,
            barmode='group',
            xaxis={'tickangle': -45},
        )
        return fig

    def create_trend_chart(self, reports: List[Dict[str, Any]], benchmark_name: str):
        """Create a time-series chart showing benchmark trends over time."""
        timestamps = []
        avg_times = []
        avg_mems = []

        for report in sorted(reports, key=lambda r: r.get('metadata', {}).get('timestamp', '')):
            benchmarks = report.get('benchmarks', report.get('results', []))
            for bench in benchmarks:
                if bench['name'] == benchmark_name:
                    ts = report.get('metadata', {}).get('timestamp') or report.get('system', {}).get('timestamp')
                    if ts:
                        timestamps.append(datetime.fromisoformat(ts))
                        avg_times.append(bench['time']['avg_sec'])
                        avg_mems.append(bench['memory']['avg_peak_mb'])
                    break

        if not timestamps:
            return None

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=avg_times,
            mode='lines+markers',
            name='Execution Time (s)',
            yaxis='y',
            marker=dict(size=8, color='#4CAF50'),
        ))
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=avg_mems,
            mode='lines+markers',
            name='Peak Memory (MB)',
            yaxis='y2',
            marker=dict(size=8, color='#2196F3'),
        ))

        fig.update_layout(
            title=f"Performance Trend: {benchmark_name}",
            xaxis=dict(title="Timestamp"),
            yaxis=dict(title="Time (seconds)", side='left'),
            yaxis2=dict(title="Memory (MB)", overlaying='y', side='right'),
            template="plotly_white",
            height=400,
            hovermode='x unified',
        )
        return fig

    def create_memory_vs_time_scatter(self, benchmarks: List[Dict[str, Any]], title: str):
        """Create a scatter plot comparing memory usage vs execution time."""
        names = [b['name'] for b in benchmarks]
        avg_times = [b['time']['avg_sec'] for b in benchmarks]
        avg_mems = [b['memory']['avg_peak_mb'] for b in benchmarks]
        iterations = [b['iterations'] for b in benchmarks]

        # Calculate efficiency score (lower is better)
        # Normalized time * normalized memory
        max_time = max(avg_times) if avg_times else 1
        max_mem = max(avg_mems) if avg_mems else 1
        efficiency_scores = [
            (t / max_time) * (m / max_mem) * 100
            for t, m in zip(avg_times, avg_mems)
        ]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=avg_times,
            y=avg_mems,
            mode='markers+text',
            text=names,
            textposition='top center',
            textfont=dict(size=9),
            marker=dict(
                size=[20 + (e * 0.5) for e in efficiency_scores],
                color=efficiency_scores,
                colorscale='RdYlGn_r',  # Red (bad) to Green (good), reversed
                showscale=True,
                colorbar=dict(title="Efficiency<br>Score"),
                line=dict(width=2, color='white'),
            ),
            customdata=list(zip(iterations, efficiency_scores)),
            hovertemplate=(
                '<b>%{text}</b><br>' +
                'Time: %{x:.4f}s<br>' +
                'Memory: %{y:.2f} MB<br>' +
                'Iterations: %{customdata[0]}<br>' +
                'Efficiency: %{customdata[1]:.1f}<br>' +
                '<extra></extra>'
            ),
        ))

        fig.update_layout(
            title=title,
            xaxis=dict(title="Average Execution Time (seconds)", type='log'),
            yaxis=dict(title="Average Peak Memory (MB)"),
            template="plotly_white",
            height=600,
            showlegend=False,
        )
        return fig

    def create_efficiency_ranking_chart(self, benchmarks: List[Dict[str, Any]]):
        """Create a horizontal bar chart ranking benchmarks by efficiency."""
        names = [b['name'] for b in benchmarks]
        avg_times = [b['time']['avg_sec'] for b in benchmarks]
        avg_mems = [b['memory']['avg_peak_mb'] for b in benchmarks]

        # Calculate efficiency metrics
        max_time = max(avg_times) if avg_times else 1
        max_mem = max(avg_mems) if avg_mems else 1

        # Efficiency score: lower is better (normalized)
        efficiency_scores = [
            ((t / max_time) + (m / max_mem)) / 2 * 100
            for t, m in zip(avg_times, avg_mems)
        ]

        # Sort by efficiency (best to worst)
        sorted_data = sorted(
            zip(names, efficiency_scores, avg_times, avg_mems),
            key=lambda x: x[1]
        )
        sorted_names, sorted_scores, sorted_times, sorted_mems = zip(*sorted_data)

        # Color code: green for efficient, red for inefficient
        colors = ['#4CAF50' if s < 50 else '#FFC107' if s < 75 else '#F44336'
                  for s in sorted_scores]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=sorted_names,
            x=sorted_scores,
            orientation='h',
            marker=dict(color=colors),
            text=[f'{s:.1f}' for s in sorted_scores],
            textposition='outside',
            customdata=list(zip(sorted_times, sorted_mems)),
            hovertemplate=(
                '<b>%{y}</b><br>' +
                'Efficiency Score: %{x:.1f}<br>' +
                'Time: %{customdata[0]:.4f}s<br>' +
                'Memory: %{customdata[1]:.2f} MB<br>' +
                '<extra></extra>'
            ),
        ))

        fig.update_layout(
            title="Benchmark Efficiency Ranking (Lower is Better)",
            xaxis=dict(title="Efficiency Score"),
            yaxis=dict(title=""),
            template="plotly_white",
            height=max(400, len(names) * 40),
            showlegend=False,
        )
        return fig

    def create_throughput_chart(self, benchmarks: List[Dict[str, Any]]):
        """Create a bar chart showing operations per second."""
        names = []
        throughputs = []

        for bench in benchmarks:
            iterations = bench['iterations']
            total_time = bench['time']['total_sec']
            if total_time > 0:
                throughput = iterations / total_time
                names.append(bench['name'])
                throughputs.append(throughput)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names,
            y=throughputs,
            marker_color='#9C27B0',
            text=[f'{t:.2f}' for t in throughputs],
            textposition='outside',
        ))

        fig.update_layout(
            title="Benchmark Throughput",
            xaxis=dict(title="Benchmark", tickangle=-45),
            yaxis=dict(title="Operations per Second"),
            template="plotly_white",
            height=500,
        )
        return fig

    def create_memory_breakdown_chart(self, benchmarks: List[Dict[str, Any]]):
        """Create a stacked bar chart showing memory breakdown."""
        names = [b['name'] for b in benchmarks]
        baseline = [b['memory']['avg_peak_mb'] - b['memory']['avg_delta_mb']
                   for b in benchmarks]
        delta = [b['memory']['avg_delta_mb'] for b in benchmarks]
        leaked = [b['memory']['max_leaked_mb'] for b in benchmarks]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Baseline Memory',
            x=names,
            y=baseline,
            marker_color='#2196F3',
        ))
        fig.add_trace(go.Bar(
            name='Operation Delta',
            x=names,
            y=delta,
            marker_color='#FFC107',
        ))
        fig.add_trace(go.Bar(
            name='Memory Leaked',
            x=names,
            y=leaked,
            marker_color='#F44336',
        ))

        fig.update_layout(
            title="Memory Usage Breakdown",
            xaxis=dict(title="Benchmark", tickangle=-45),
            yaxis=dict(title="Memory (MB)"),
            barmode='stack',
            template="plotly_white",
            height=500,
        )
        return fig


def render_sidebar(analyzer: BenchmarkAnalyzer):
    """Render the sidebar with navigation and filters."""
    st.sidebar.title("📊 Benchmark Dashboard")
    st.sidebar.markdown("---")

    # Navigation
    page = st.sidebar.radio(
        "Navigate",
        ["Overview", "Suite Analysis", "Function Comparison", "Benchmark Trends", "System Comparison", "Raw Data"]
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Total Reports:** {len(analyzer.reports)}")
    st.sidebar.markdown(f"**Suites Found:** {len(analyzer.get_suite_names())}")

    return page


def render_overview(analyzer: BenchmarkAnalyzer):
    """Render the overview page."""
    st.title("📊 Benchmark Overview")

    if not analyzer.reports:
        st.warning("No benchmark reports found. Run benchmarks with --save flag to generate reports.")
        st.code("python backend/benchmark/run_all.py --save")
        return

    # Latest reports summary
    st.header("Latest Benchmark Results")

    suites = analyzer.get_suite_names()

    cols = st.columns(len(suites) if suites else 1)

    for idx, suite_name in enumerate(suites):
        with cols[idx]:
            reports = analyzer.get_reports_by_suite(suite_name)
            if reports:
                latest = reports[0]

                # Extract summary data
                if 'summary' in latest:
                    summary = latest['summary']
                    st.metric(
                        label=f"{suite_name}",
                        value=f"{summary['total_execution_time_sec']:.2f}s",
                        delta=f"{summary['benchmarks_passed']} benchmarks"
                    )
                    st.caption(f"Peak: {summary['max_peak_memory_mb']:.1f} MB")
                else:
                    st.metric(
                        label=f"{suite_name}",
                        value=f"{len(latest.get('results', []))} benchmarks"
                    )

    st.markdown("---")

    # Performance Insights
    st.header("Performance Insights")

    for suite_name in suites:
        reports = analyzer.get_reports_by_suite(suite_name)
        if reports:
            latest = reports[0]

            if 'performance_insights' in latest:
                insights = latest['performance_insights']

                with st.expander(f"🔍 {suite_name} Insights", expanded=True):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("⚡ Speed")
                        if insights.get('fastest_benchmark'):
                            st.success(f"**Fastest:** {insights['fastest_benchmark']['name']}")
                            st.caption(f"{insights['fastest_benchmark']['avg_time_sec']:.4f}s")
                        if insights.get('slowest_benchmark'):
                            st.warning(f"**Slowest:** {insights['slowest_benchmark']['name']}")
                            st.caption(f"{insights['slowest_benchmark']['avg_time_sec']:.4f}s")

                    with col2:
                        st.subheader("💾 Memory")
                        if insights.get('most_memory_efficient'):
                            st.success(f"**Most Efficient:** {insights['most_memory_efficient']['name']}")
                            st.caption(f"{insights['most_memory_efficient']['avg_peak_mb']:.2f} MB")
                        if insights.get('most_memory_intensive'):
                            st.warning(f"**Most Intensive:** {insights['most_memory_intensive']['name']}")
                            st.caption(f"{insights['most_memory_intensive']['avg_peak_mb']:.2f} MB")

                    # Memory leaks
                    if insights.get('potential_memory_leaks'):
                        st.error("⚠️ **Potential Memory Leaks Detected:**")
                        for leak in insights['potential_memory_leaks']:
                            st.markdown(f"- `{leak['name']}`: **{leak['leaked_mb']:.2f} MB** leaked")


def render_suite_analysis(analyzer: BenchmarkAnalyzer):
    """Render detailed suite analysis page."""
    st.title("🔬 Suite Analysis")

    suites = analyzer.get_suite_names()
    if not suites:
        st.warning("No benchmark suites found.")
        return

    selected_suite = st.selectbox("Select Benchmark Suite", suites)

    reports = analyzer.get_reports_by_suite(selected_suite)
    if not reports:
        st.warning(f"No reports found for suite: {selected_suite}")
        return

    latest = reports[0]
    benchmarks = latest.get('benchmarks', latest.get('results', []))

    # Suite metadata
    st.header(f"📋 {selected_suite}")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        timestamp = latest.get('metadata', {}).get('timestamp') or latest.get('system', {}).get('timestamp')
        st.metric("Last Run", timestamp.split('T')[0] if timestamp else "N/A")

    with col2:
        st.metric("Total Benchmarks", len(benchmarks))

    with col3:
        if 'summary' in latest:
            st.metric("Total Time", f"{latest['summary']['total_execution_time_sec']:.2f}s")

    with col4:
        if 'summary' in latest:
            st.metric("Peak Memory", f"{latest['summary']['max_peak_memory_mb']:.1f} MB")

    # System Information
    with st.expander("🖥️ System Information"):
        system = latest.get('system', {})
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Platform:** {system.get('platform', 'N/A')}")
            st.markdown(f"**Python:** {system.get('python', 'N/A')}")
            st.markdown(f"**CPU:** {system.get('cpu', 'N/A')}")
            st.markdown(f"**CPU Threads:** {system.get('cpu_threads', 'N/A')}")

        with col2:
            st.markdown(f"**RAM:** {system.get('ram_gb', 'N/A')} GB")
            st.markdown(f"**GPU:** {system.get('gpu', 'N/A')}")
            if 'cuda_version' in system:
                st.markdown(f"**CUDA:** {system.get('cuda_version', 'N/A')}")
                st.markdown(f"**VRAM:** {system.get('vram_gb', 'N/A')} GB")

    st.markdown("---")

    # Visualizations
    st.header("📈 Performance Charts")

    tab1, tab2, tab3 = st.tabs(["⏱️ Execution Time", "💾 Memory Usage", "📊 Detailed Stats"])

    with tab1:
        fig = analyzer.create_time_comparison_chart(benchmarks, f"{selected_suite} - Execution Time")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig = analyzer.create_memory_comparison_chart(benchmarks, f"{selected_suite} - Memory Usage")
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        # Create detailed DataFrame
        data = []
        for bench in benchmarks:
            data.append({
                'Benchmark': bench['name'],
                'Iterations': bench['iterations'],
                'Avg Time (s)': bench['time']['avg_sec'],
                'Min Time (s)': bench['time']['min_sec'],
                'Max Time (s)': bench['time']['max_sec'],
                'Avg Peak Mem (MB)': bench['memory']['avg_peak_mb'],
                'Max Peak Mem (MB)': bench['memory']['max_peak_mb'],
                'Memory Leaked (MB)': bench['memory']['max_leaked_mb'],
            })

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=400)

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"{selected_suite}_benchmarks.csv",
            mime="text/csv",
        )


def render_benchmark_trends(analyzer: BenchmarkAnalyzer):
    """Render benchmark trends over time."""
    st.title("📈 Benchmark Trends")

    suites = analyzer.get_suite_names()
    if not suites:
        st.warning("No benchmark suites found.")
        return

    selected_suite = st.selectbox("Select Benchmark Suite", suites, key="trend_suite")

    reports = analyzer.get_reports_by_suite(selected_suite)
    if len(reports) < 2:
        st.info("Need at least 2 benchmark runs to show trends. Run benchmarks multiple times to see trends.")
        return

    # Get all benchmark names
    all_benchmarks = set()
    for report in reports:
        benchmarks = report.get('benchmarks', report.get('results', []))
        for bench in benchmarks:
            all_benchmarks.add(bench['name'])

    selected_benchmark = st.selectbox("Select Benchmark", sorted(all_benchmarks))

    # Create trend chart
    fig = analyzer.create_trend_chart(reports, selected_benchmark)

    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No trend data available for this benchmark.")

    # Historical comparison table
    st.subheader("📋 Historical Data")

    history_data = []
    for report in sorted(reports, key=lambda r: r.get('metadata', {}).get('timestamp', ''), reverse=True):
        benchmarks = report.get('benchmarks', report.get('results', []))
        for bench in benchmarks:
            if bench['name'] == selected_benchmark:
                ts = report.get('metadata', {}).get('timestamp') or report.get('system', {}).get('timestamp')
                history_data.append({
                    'Timestamp': ts,
                    'Avg Time (s)': bench['time']['avg_sec'],
                    'Peak Memory (MB)': bench['memory']['avg_peak_mb'],
                    'Memory Leaked (MB)': bench['memory']['max_leaked_mb'],
                })
                break

    if history_data:
        df = pd.DataFrame(history_data)
        st.dataframe(df, use_container_width=True)


def render_system_comparison(analyzer: BenchmarkAnalyzer):
    """Compare benchmark results across different systems."""
    st.title("🖥️ System Comparison")

    if len(analyzer.reports) < 2:
        st.info("Need at least 2 benchmark reports to compare systems.")
        return

    # Group reports by system configuration
    st.subheader("📊 Performance Across Systems")

    system_data = []
    for report in analyzer.reports:
        system = report.get('system', {})
        summary = report.get('summary', {})

        system_data.append({
            'Suite': report.get('metadata', {}).get('suite_name') or report.get('suite', 'Unknown'),
            'Timestamp': (report.get('metadata', {}).get('timestamp') or
                         report.get('system', {}).get('timestamp', 'Unknown')),
            'CPU': system.get('cpu', 'Unknown')[:50],
            'GPU': system.get('gpu', 'Unknown')[:30],
            'RAM (GB)': system.get('ram_gb', 0),
            'Total Time (s)': summary.get('total_execution_time_sec', 0),
            'Peak Memory (MB)': summary.get('max_peak_memory_mb', 0),
        })

    df = pd.DataFrame(system_data)
    st.dataframe(df, use_container_width=True, height=400)


def render_function_comparison(analyzer: BenchmarkAnalyzer):
    """Render comprehensive function comparison page."""
    st.title("⚖️ Function Comparison: Memory vs Compute Time")

    suites = analyzer.get_suite_names()
    if not suites:
        st.warning("No benchmark suites found.")
        return

    # Add "All Suites" option
    suite_options = ["All Suites"] + suites
    selected_option = st.selectbox("Select Benchmark Suite", suite_options, key="comparison_suite")

    # Gather benchmarks based on selection
    benchmarks = []
    if selected_option == "All Suites":
        # Combine benchmarks from all suites
        for suite in suites:
            reports = analyzer.get_reports_by_suite(suite)
            if reports:
                latest = reports[0]
                suite_benchmarks = latest.get('benchmarks', latest.get('results', []))
                # Add suite name prefix to distinguish benchmarks from different suites
                for b in suite_benchmarks:
                    b_copy = b.copy()
                    b_copy['name'] = f"[{suite}] {b['name']}"
                    b_copy['_original_suite'] = suite
                    benchmarks.append(b_copy)
    else:
        reports = analyzer.get_reports_by_suite(selected_option)
        if not reports:
            st.warning(f"No reports found for suite: {selected_option}")
            return
        latest = reports[0]
        benchmarks = latest.get('benchmarks', latest.get('results', []))

    if not benchmarks:
        st.warning("No benchmarks found.")
        return

    # Overview metrics
    if selected_option == "All Suites":
        st.header(f"📊 Performance Overview - All {len(benchmarks)} Benchmarks")
    else:
        st.header(f"📊 Performance Overview - {selected_option}")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_time = sum(b['time']['total_sec'] for b in benchmarks)
        st.metric("Total Time", f"{total_time:.2f}s")

    with col2:
        avg_time = sum(b['time']['avg_sec'] for b in benchmarks) / len(benchmarks)
        st.metric("Avg Time", f"{avg_time:.4f}s")

    with col3:
        max_mem = max(b['memory']['avg_peak_mb'] for b in benchmarks)
        st.metric("Peak Memory", f"{max_mem:.1f} MB")

    with col4:
        total_leaked = sum(b['memory']['max_leaked_mb'] for b in benchmarks)
        st.metric("Total Leaked", f"{total_leaked:.2f} MB")

    st.markdown("---")

    # Main comparison visualizations
    st.header("🔍 Comparative Analysis")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Memory vs Time",
        "🏆 Efficiency Ranking",
        "⚡ Throughput",
        "💾 Memory Breakdown",
        "📋 Comparison Table"
    ])

    with tab1:
        st.subheader("Memory Usage vs Execution Time")
        st.markdown("""
        This scatter plot shows the relationship between memory usage and execution time.
        - **Bubble size** represents efficiency (larger = less efficient)
        - **Color** indicates efficiency score (green = good, red = poor)
        - **Position** shows time (x-axis) and memory (y-axis)

        **Ideal benchmarks** are in the bottom-left (low time, low memory).
        """)

        fig = analyzer.create_memory_vs_time_scatter(
            benchmarks,
            f"{selected_option} - Memory vs Execution Time"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Add insights
        with st.expander("💡 Interpretation Guide"):
            st.markdown("""
            **Quadrant Analysis:**
            - **Bottom-Left**: ✅ Fast & memory-efficient (optimal)
            - **Bottom-Right**: ⚠️ Slow but memory-efficient
            - **Top-Left**: ⚠️ Fast but memory-intensive
            - **Top-Right**: ❌ Slow & memory-intensive (needs optimization)

            **Efficiency Score:**
            - **< 50**: Good efficiency
            - **50-75**: Moderate efficiency
            - **> 75**: Poor efficiency (optimization target)
            """)

    with tab2:
        st.subheader("Efficiency Ranking")
        st.markdown("""
        Benchmarks ranked by overall efficiency (combination of time and memory).
        - **Green**: Highly efficient (< 50)
        - **Yellow**: Moderately efficient (50-75)
        - **Red**: Needs optimization (> 75)
        """)

        fig = analyzer.create_efficiency_ranking_chart(benchmarks)
        st.plotly_chart(fig, use_container_width=True)

        # Show top performers
        avg_times = [b['time']['avg_sec'] for b in benchmarks]
        avg_mems = [b['memory']['avg_peak_mb'] for b in benchmarks]
        max_time = max(avg_times) if avg_times else 1
        max_mem = max(avg_mems) if avg_mems else 1

        efficiency_data = []
        for b in benchmarks:
            score = ((b['time']['avg_sec'] / max_time) +
                    (b['memory']['avg_peak_mb'] / max_mem)) / 2 * 100
            efficiency_data.append({
                'name': b['name'],
                'score': score,
                'time': b['time']['avg_sec'],
                'memory': b['memory']['avg_peak_mb']
            })

        efficiency_data.sort(key=lambda x: x['score'])

        col1, col2 = st.columns(2)
        with col1:
            st.success("🏆 **Most Efficient**")
            top_3 = efficiency_data[:3]
            for i, item in enumerate(top_3, 1):
                st.markdown(f"{i}. **{item['name']}** (Score: {item['score']:.1f})")
                st.caption(f"   Time: {item['time']:.4f}s | Memory: {item['memory']:.2f} MB")

        with col2:
            st.error("⚠️ **Needs Optimization**")
            bottom_3 = efficiency_data[-3:]
            bottom_3.reverse()
            for i, item in enumerate(bottom_3, 1):
                st.markdown(f"{i}. **{item['name']}** (Score: {item['score']:.1f})")
                st.caption(f"   Time: {item['time']:.4f}s | Memory: {item['memory']:.2f} MB")

    with tab3:
        st.subheader("Operations per Second")
        st.markdown("Higher throughput indicates better performance for repetitive operations.")

        fig = analyzer.create_throughput_chart(benchmarks)
        st.plotly_chart(fig, use_container_width=True)

        # Calculate and show throughput stats
        throughputs = []
        for b in benchmarks:
            if b['time']['total_sec'] > 0:
                throughput = b['iterations'] / b['time']['total_sec']
                throughputs.append({
                    'name': b['name'],
                    'throughput': throughput,
                    'iterations': b['iterations']
                })

        throughputs.sort(key=lambda x: x['throughput'], reverse=True)

        st.info(f"**Highest Throughput**: {throughputs[0]['name']} at {throughputs[0]['throughput']:.2f} ops/sec")

    with tab4:
        st.subheader("Memory Usage Breakdown")
        st.markdown("""
        Breakdown of memory usage components:
        - **Baseline**: Memory at start
        - **Operation Delta**: Memory increase during operation
        - **Leaked**: Memory not released after operation
        """)

        fig = analyzer.create_memory_breakdown_chart(benchmarks)
        st.plotly_chart(fig, use_container_width=True)

        # Memory leak warning
        leaked_benchmarks = [b for b in benchmarks if b['memory']['max_leaked_mb'] > 5.0]
        if leaked_benchmarks:
            st.warning(f"⚠️ **{len(leaked_benchmarks)} benchmark(s)** showing significant memory leaks (>5MB)")
            for b in leaked_benchmarks:
                st.markdown(f"- `{b['name']}`: {b['memory']['max_leaked_mb']:.2f} MB leaked")

    with tab5:
        st.subheader("Detailed Comparison Table")

        # Create comprehensive comparison table
        comparison_data = []
        for b in benchmarks:
            # Calculate metrics
            throughput = b['iterations'] / b['time']['total_sec'] if b['time']['total_sec'] > 0 else 0
            time_variance = ((b['time']['max_sec'] - b['time']['min_sec']) / b['time']['avg_sec'] * 100) if b['time']['avg_sec'] > 0 else 0

            comparison_data.append({
                'Function': b['name'],
                'Avg Time (s)': b['time']['avg_sec'],
                'Time Variance (%)': time_variance,
                'Throughput (ops/s)': throughput,
                'Avg Memory (MB)': b['memory']['avg_peak_mb'],
                'Memory Delta (MB)': b['memory']['avg_delta_mb'],
                'Leaked (MB)': b['memory']['max_leaked_mb'],
                'Iterations': b['iterations'],
            })

        df = pd.DataFrame(comparison_data)

        # Style the dataframe
        st.dataframe(
            df.style.background_gradient(subset=['Avg Time (s)'], cmap='RdYlGn_r')
              .background_gradient(subset=['Avg Memory (MB)'], cmap='RdYlGn_r')
              .background_gradient(subset=['Leaked (MB)'], cmap='RdYlGn_r')
              .background_gradient(subset=['Throughput (ops/s)'], cmap='RdYlGn')
              .format({
                  'Avg Time (s)': '{:.4f}',
                  'Time Variance (%)': '{:.1f}',
                  'Throughput (ops/s)': '{:.2f}',
                  'Avg Memory (MB)': '{:.2f}',
                  'Memory Delta (MB)': '{:.2f}',
                  'Leaked (MB)': '{:.2f}',
              }),
            use_container_width=True,
            height=400
        )

        # Export options
        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"{selected_option.replace(' ', '_').lower()}_comparison.csv",
                mime="text/csv",
            )

        with col2:
            # Calculate summary statistics
            st.metric("Functions Analyzed", len(df))

    # Performance recommendations
    st.markdown("---")
    st.header("💡 Optimization Recommendations")

    # Find optimization targets
    high_time_benchmarks = [b for b in benchmarks if b['time']['avg_sec'] > avg_time * 1.5]
    high_mem_benchmarks = [b for b in benchmarks if b['memory']['avg_peak_mb'] > max_mem * 0.7]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⏱️ Time Optimization Targets")
        if high_time_benchmarks:
            for b in high_time_benchmarks:
                st.warning(f"**{b['name']}**: {b['time']['avg_sec']:.4f}s (>{avg_time*1.5:.4f}s threshold)")
        else:
            st.success("All benchmarks perform within acceptable time ranges")

    with col2:
        st.subheader("💾 Memory Optimization Targets")
        if high_mem_benchmarks:
            for b in high_mem_benchmarks:
                st.warning(f"**{b['name']}**: {b['memory']['avg_peak_mb']:.2f} MB")
        else:
            st.success("All benchmarks use memory efficiently")


def render_raw_data(analyzer: BenchmarkAnalyzer):
    """Display raw JSON data."""
    st.title("📄 Raw Data Viewer")

    if not analyzer.reports:
        st.warning("No reports available.")
        return

    report_names = [r['_file_name'] for r in analyzer.reports]
    selected_report = st.selectbox("Select Report", report_names)

    # Find the selected report
    report = next((r for r in analyzer.reports if r['_file_name'] == selected_report), None)

    if report:
        st.json(report)

        # Download button
        st.download_button(
            label="📥 Download JSON",
            data=json.dumps(report, indent=2),
            file_name=selected_report,
            mime="application/json",
        )


def main():
    """Main dashboard application."""
    # Setup results directory
    results_dir = Path(__file__).parent.parent / "benchmark" / "results"

    # Initialize analyzer
    analyzer = BenchmarkAnalyzer(results_dir)

    # Render sidebar
    page = render_sidebar(analyzer)

    # Render selected page
    if page == "Overview":
        render_overview(analyzer)
    elif page == "Suite Analysis":
        render_suite_analysis(analyzer)
    elif page == "Function Comparison":
        render_function_comparison(analyzer)
    elif page == "Benchmark Trends":
        render_benchmark_trends(analyzer)
    elif page == "System Comparison":
        render_system_comparison(analyzer)
    elif page == "Raw Data":
        render_raw_data(analyzer)


if __name__ == "__main__":
    main()
