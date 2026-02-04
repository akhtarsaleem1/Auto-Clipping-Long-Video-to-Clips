"""
Spike detection module.

Identifies moments where crowd audio significantly exceeds the baseline,
indicating exciting moments like cheers, chants, or reactions.

Enhanced with derivative-based detection for sudden audio spikes.
"""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np


@dataclass
class Spike:
    """Represents a detected audio spike (potential exciting moment)."""
    start_time: float  # Start of the spike in seconds
    end_time: float    # End of the spike in seconds
    peak_time: float   # Time of maximum energy
    peak_energy: float # Maximum energy value
    avg_energy: float  # Average energy during spike
    score: float       # Excitement score (higher = more exciting)


def detect_spikes(
    energy: np.ndarray,
    times: np.ndarray,
    baseline: np.ndarray,
    threshold_multiplier: float = 1.5,
    min_duration: float = 0.5,
    derivative: Optional[np.ndarray] = None,
    derivative_weight: float = 0.3
) -> List[Spike]:
    """
    Detect moments where energy significantly exceeds baseline.
    
    Args:
        energy: RMS energy values
        times: Corresponding timestamps
        baseline: Baseline energy values
        threshold_multiplier: How many times above baseline to trigger
        min_duration: Minimum spike duration in seconds
        derivative: Optional rate-of-change array for detecting sudden changes
        derivative_weight: How much to weight derivative vs absolute energy
        
    Returns:
        List of detected Spike objects
    """
    # Compute combined score: energy + derivative bonus
    if derivative is not None and len(derivative) == len(energy):
        # Normalize derivative
        deriv_max = np.max(derivative) if np.max(derivative) > 0 else 1.0
        deriv_normalized = derivative / deriv_max
        
        # Combine: energy matters most, but sudden changes get bonus
        combined = energy * (1.0 + derivative_weight * deriv_normalized)
    else:
        combined = energy
    
    # Find where combined score exceeds threshold
    threshold = baseline * threshold_multiplier
    above_threshold = combined > threshold
    
    # Find contiguous regions above threshold
    spikes = []
    in_spike = False
    spike_start_idx = 0
    
    for i in range(len(above_threshold)):
        if above_threshold[i] and not in_spike:
            # Start of a new spike
            in_spike = True
            spike_start_idx = i
        elif not above_threshold[i] and in_spike:
            # End of spike
            in_spike = False
            spike_end_idx = i
            
            # Create spike if it meets minimum duration
            spike = _create_spike(
                energy, times, spike_start_idx, spike_end_idx, baseline, derivative
            )
            if spike and (spike.end_time - spike.start_time) >= min_duration:
                spikes.append(spike)
    
    # Handle spike that extends to end
    if in_spike:
        spike = _create_spike(
            energy, times, spike_start_idx, len(energy), baseline, derivative
        )
        if spike and (spike.end_time - spike.start_time) >= min_duration:
            spikes.append(spike)
    
    return spikes


def _create_spike(
    energy: np.ndarray,
    times: np.ndarray,
    start_idx: int,
    end_idx: int,
    baseline: np.ndarray,
    derivative: Optional[np.ndarray] = None
) -> Spike:
    """Create a Spike object from indices."""
    if start_idx >= end_idx or start_idx >= len(times):
        return None
    
    end_idx = min(end_idx, len(times))
    
    spike_energy = energy[start_idx:end_idx]
    spike_baseline = baseline[start_idx:end_idx]
    
    peak_idx = np.argmax(spike_energy)
    peak_energy = spike_energy[peak_idx]
    avg_energy = np.mean(spike_energy)
    avg_baseline = np.mean(spike_baseline)
    
    # Score based on how much energy exceeds baseline
    # Higher score = more exciting moment
    energy_ratio = avg_energy / avg_baseline if avg_baseline > 0 else 1.0
    duration_factor = np.sqrt(end_idx - start_idx)
    
    # Bonus for sudden onset (derivative spike)
    derivative_bonus = 1.0
    if derivative is not None and len(derivative) > start_idx:
        max_deriv = np.max(derivative[start_idx:min(start_idx + 10, end_idx)])
        avg_deriv = np.mean(derivative)
        if avg_deriv > 0:
            derivative_bonus = 1.0 + min(max_deriv / avg_deriv, 2.0) * 0.2
    
    score = energy_ratio * duration_factor * derivative_bonus
    
    return Spike(
        start_time=times[start_idx],
        end_time=times[end_idx - 1] if end_idx <= len(times) else times[-1],
        peak_time=times[start_idx + peak_idx],
        peak_energy=float(peak_energy),
        avg_energy=float(avg_energy),
        score=float(score)
    )


def merge_nearby_spikes(
    spikes: List[Spike],
    min_gap_seconds: float = 2.0
) -> List[Spike]:
    """
    Merge spikes that are close together into single events.
    
    This helps combine related moments (e.g., setup + reaction).
    
    Args:
        spikes: List of detected spikes
        min_gap_seconds: Minimum gap between spikes to keep them separate
        
    Returns:
        Merged list of spikes
    """
    if not spikes:
        return []
    
    # Sort by start time
    sorted_spikes = sorted(spikes, key=lambda s: s.start_time)
    merged = [sorted_spikes[0]]
    
    for spike in sorted_spikes[1:]:
        last = merged[-1]
        
        # Check if this spike should be merged with the previous one
        gap = spike.start_time - last.end_time
        
        if gap <= min_gap_seconds:
            # Merge: extend the last spike
            merged[-1] = Spike(
                start_time=last.start_time,
                end_time=spike.end_time,
                peak_time=last.peak_time if last.peak_energy > spike.peak_energy else spike.peak_time,
                peak_energy=max(last.peak_energy, spike.peak_energy),
                avg_energy=(last.avg_energy + spike.avg_energy) / 2,
                score=last.score + spike.score  # Combine scores
            )
        else:
            merged.append(spike)
    
    return merged


def filter_spikes(
    spikes: List[Spike],
    min_score: float = None,
    min_duration: float = 0.5,
    max_count: int = None
) -> List[Spike]:
    """
    Filter and rank spikes to get the best moments.
    
    Args:
        spikes: List of spikes to filter
        min_score: Minimum score to keep (None = no minimum)
        min_duration: Minimum duration in seconds
        max_count: Maximum number of spikes to return (None = all)
        
    Returns:
        Filtered and sorted list of spikes (best first)
    """
    filtered = spikes
    
    # Filter by duration
    filtered = [s for s in filtered if (s.end_time - s.start_time) >= min_duration]
    
    # Filter by score
    if min_score is not None:
        filtered = [s for s in filtered if s.score >= min_score]
    
    # Sort by score (highest first)
    filtered = sorted(filtered, key=lambda s: s.score, reverse=True)
    
    # Limit count
    if max_count is not None:
        filtered = filtered[:max_count]
    
    return filtered


def rank_spikes_by_excitement(spikes: List[Spike]) -> List[Spike]:
    """
    Rank spikes by excitement level (best moments first).
    
    Considers:
    - Peak energy (louder = more exciting)
    - Duration (sustained excitement is better)
    - Energy consistency (avoid brief spikes)
    
    Returns:
        Sorted list with most exciting moments first
    """
    return sorted(spikes, key=lambda s: s.score, reverse=True)
