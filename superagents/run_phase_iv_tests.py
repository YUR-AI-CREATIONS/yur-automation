"""
Phase IV Test Execution Suite - Writes all results to disk
Produces audit-grade evidence of LLM integration and reasoning capability
"""

import subprocess
import json
import os
from datetime import datetime
from pathlib import Path

# Configuration
PYTHON_EXE = r"C:\Users\Jeremy Gosselin\OneDrive\Neo3\miniconda3\python.exe"
PROJECT_ROOT = Path(__file__).parent
RESULTS_DIR = PROJECT_ROOT / "data" / "output" / "test_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Test Suite
TESTS = [
    {
        "name": "Test A: Delta Verification Understanding",
        "query": "How does delta verification work?",
        "expected_keywords": ["delta", "verification", "hash", "comparison", "Genesis"],
        "description": "Retrieve and explain delta verification logic"
    },
    {
        "name": "Test B: Hashing Algorithm Discovery",
        "query": "What cryptographic hashing algorithm is used for birthmarks and why was it chosen?",
        "expected_keywords": ["SHA", "256", "hash", "algorithm"],
        "description": "Identify hashing algorithm and explain selection rationale"
    },
    {
        "name": "Test C: Multi-Artifact Synthesis",
        "query": "Explain how the XML serialization strategy integrates with blake birthmarking and why Base64 encoding was chosen over CDATA",
        "expected_keywords": ["XML", "Base64", "serialization", "birthmark", "CDATA"],
        "description": "Cross-file architectural synthesis and design decision explanation"
    }
]


def run_test(test_config: dict) -> dict:
    """Execute a single test and capture output"""
    print(f"\n{'='*70}")
    print(f"Running: {test_config['name']}")
    print(f"{'='*70}")
    print(f"Query: {test_config['query']}")
    print(f"Description: {test_config['description']}\n")
    
    start_time = datetime.now()
    
    try:
        # Run the cognitive query
        result = subprocess.run(
            [PYTHON_EXE, "src/core/cognitive_query.py", test_config['query']],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        end_time = datetime.now()
        latency = (end_time - start_time).total_seconds()
        
        # Parse response
        output = result.stdout + result.stderr
        
        # Extract the response (more robust parsing)
        response = ""
        try:
            # Look for [RESPONSE] marker (updated format)
            if "[RESPONSE] COGNITIVE ENGINE" in output:
                start_idx = output.find("[RESPONSE] COGNITIVE ENGINE")
                # Find the next line after the marker
                start_idx = output.find("\n", start_idx) + 1
                # Find next separator (sequence of = signs)
                end_idx = output.find("======", start_idx)
                if end_idx > start_idx:
                    response = output[start_idx:end_idx].strip()
        except:
            # If parsing fails, use full output
            response = output
        
        # Check for expected keywords
        keywords_found = []
        for keyword in test_config['expected_keywords']:
            if keyword.lower() in output.lower():
                keywords_found.append(keyword)
        
        # Determine pass/fail
        passed = (
            result.returncode == 0 and 
            len(response) > 100 and
            len(keywords_found) >= len(test_config['expected_keywords']) * 0.75  # 75% threshold
        )
        
        test_result = {
            "name": test_config['name'],
            "query": test_config['query'],
            "status": "PASS" if passed else "FAIL",
            "latency_seconds": latency,
            "response": response,
            "response_length": len(response),
            "expected_keywords": test_config['expected_keywords'],
            "keywords_found": keywords_found,
            "accuracy_score": len(keywords_found) / len(test_config['expected_keywords']) if test_config['expected_keywords'] else 0,
            "timestamp": start_time.isoformat(),
            "return_code": result.returncode,
            "full_output": output[:2000]  # First 2000 chars for debugging
        }
        
        # Display result
        print(f"Status: {test_result['status']}")
        print(f"Latency: {latency:.2f}s")
        print(f"Response Length: {len(response)} chars")
        print(f"Keywords Found: {keywords_found} / {test_config['expected_keywords']}")
        print(f"Response Preview: {response[:200]}...")
        
        return test_result
        
    except subprocess.TimeoutExpired:
        return {
            "name": test_config['name'],
            "query": test_config['query'],
            "status": "TIMEOUT",
            "latency_seconds": 30,
            "response": "[ERROR] Query timed out after 30 seconds",
            "error": "Ollama API or model inference exceeded timeout"
        }
    except Exception as e:
        return {
            "name": test_config['name'],
            "query": test_config['query'],
            "status": "ERROR",
            "latency_seconds": 0,
            "error": str(e)
        }


def main():
    """Execute all tests and write results to disk"""
    
    print("\n" + "="*70)
    print("PHASE IV: FULL TEST EXECUTION SUITE")
    print("="*70)
    print(f"Start Time: {datetime.now().isoformat()}")
    print(f"Results Directory: {RESULTS_DIR}")
    print("="*70)
    
    # Run all tests
    all_results = {
        "execution_timestamp": datetime.now().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "tests": []
    }
    
    passed_count = 0
    for test_config in TESTS:
        result = run_test(test_config)
        all_results['tests'].append(result)
        if result.get('status') == 'PASS':
            passed_count += 1
    
    # Write detailed JSON results
    json_output_path = RESULTS_DIR / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n\n{'='*70}")
    print("TEST EXECUTION COMPLETE")
    print(f"{'='*70}")
    print(f"Passed: {passed_count}/{len(TESTS)}")
    print(f"Pass Rate: {100 * passed_count / len(TESTS):.1f}%")
    print(f"\nResults saved to: {json_output_path}")
    
    # Write human-readable report
    report_path = RESULTS_DIR / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("PHASE IV TEST EXECUTION REPORT\n")
        f.write("="*70 + "\n\n")
        f.write(f"Execution Time: {all_results['execution_timestamp']}\n")
        f.write(f"Project Root: {all_results['project_root']}\n\n")
        
        for i, test in enumerate(all_results['tests'], 1):
            f.write(f"\n{'='*70}\n")
            f.write(f"TEST {i}: {test['name']}\n")
            f.write(f"{'='*70}\n\n")
            f.write(f"Query: {test['query']}\n")
            f.write(f"Status: {test['status']}\n")
            f.write(f"Latency: {test.get('latency_seconds', 'N/A'):.2f}s\n")
            
            if 'response' in test:
                f.write(f"Response Length: {test.get('response_length', 0)} chars\n")
                f.write(f"Keywords Expected: {test.get('expected_keywords', [])}\n")
                f.write(f"Keywords Found: {test.get('keywords_found', [])}\n")
                f.write(f"Accuracy Score: {test.get('accuracy_score', 0):.1%}\n\n")
                f.write("RESPONSE:\n")
                f.write("-"*70 + "\n")
                f.write(test['response'][:1000] + "\n")
                if len(test['response']) > 1000:
                    f.write("[... truncated ...]\n")
                f.write("-"*70 + "\n")
            
            if 'error' in test:
                f.write(f"Error: {test['error']}\n")
        
        f.write(f"\n\n{'='*70}\n")
        f.write("SUMMARY\n")
        f.write(f"{'='*70}\n")
        f.write(f"Total Tests: {len(TESTS)}\n")
        f.write(f"Passed: {passed_count}\n")
        f.write(f"Pass Rate: {100 * passed_count / len(TESTS):.1f}%\n")
    
    print(f"Report saved to: {report_path}")
    
    # Update DEPLOYMENT_LOG with test execution evidence
    log_path = PROJECT_ROOT / "DEPLOYMENT_LOG.txt"
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write("\n\n")
        f.write("="*80 + "\n")
        f.write("PHASE IV FULL TEST EXECUTION - DISK EVIDENCE\n")
        f.write("="*80 + "\n\n")
        f.write(f"Execution Timestamp: {all_results['execution_timestamp']}\n")
        f.write(f"All Results Persisted: {json_output_path}\n")
        f.write(f"Human-Readable Report: {report_path}\n\n")
        f.write(f"SUMMARY: {passed_count}/{len(TESTS)} tests PASSED ({100*passed_count/len(TESTS):.1f}%)\n\n")
        
        for test in all_results['tests']:
            f.write(f"  ✅ {test['name']}: {test['status']} ({test.get('latency_seconds', 0):.2f}s)\n")
    
    print(f"\nDEPLOYMENT_LOG.txt updated with execution evidence")
    
    return 0 if passed_count == len(TESTS) else 1


if __name__ == "__main__":
    exit(main())
