"""
Chart analysis utilities for identifying key levels and structures
Used for dynamic take profit placement based on actual price action
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def find_swing_points(df, lookback=20, threshold=0.001):
    """
    Identify swing highs and swing lows in price data

    Args:
        df: OHLCV DataFrame
        lookback: Number of candles to look back for swing validation
        threshold: Minimum price change to qualify as swing (as decimal)

    Returns:
        Dict with 'highs' and 'lows' DataFrames containing swing points
    """
    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(df) - lookback):
        # Check for swing high
        current_high = df.iloc[i]['high']
        is_swing_high = True

        for j in range(max(0, i - lookback), min(len(df), i + lookback + 1)):
            if j != i and df.iloc[j]['high'] > current_high:
                is_swing_high = False
                break

        if is_swing_high:
            swing_highs.append({
                'index': i,
                'timestamp': df.iloc[i]['timestamp'],
                'price': current_high,
                'type': 'swing_high'
            })

        # Check for swing low
        current_low = df.iloc[i]['low']
        is_swing_low = True

        for j in range(max(0, i - lookback), min(len(df), i + lookback + 1)):
            if j != i and df.iloc[j]['low'] < current_low:
                is_swing_low = False
                break

        if is_swing_low:
            swing_lows.append({
                'index': i,
                'timestamp': df.iloc[i]['timestamp'],
                'price': current_low,
                'type': 'swing_low'
            })

    return {
        'highs': pd.DataFrame(swing_highs) if swing_highs else pd.DataFrame(),
        'lows': pd.DataFrame(swing_lows) if swing_lows else pd.DataFrame()
    }


def find_equal_levels(swing_points, tolerance=0.002):
    """
    Find equal highs/lows (liquidity pools) from swing points

    Args:
        swing_points: List of swing point dicts
        tolerance: Price tolerance for considering levels equal (as decimal)

    Returns:
        List of equal level zones
    """
    if not swing_points or len(swing_points) < 2:
        return []

    equal_levels = []
    used_indices = set()

    for i, point1 in enumerate(swing_points):
        if i in used_indices:
            continue

        cluster = [point1]
        price1 = point1['price']

        for j, point2 in enumerate(swing_points[i+1:], start=i+1):
            if j in used_indices:
                continue

            price2 = point2['price']
            price_diff = abs(price1 - price2) / price1

            if price_diff <= tolerance:
                cluster.append(point2)
                used_indices.add(j)

        if len(cluster) >= 2:
            avg_price = sum(p['price'] for p in cluster) / len(cluster)
            equal_levels.append({
                'price': avg_price,
                'count': len(cluster),
                'type': cluster[0]['type'],
                'strength': len(cluster)  # More touches = stronger level
            })

    return equal_levels


def find_round_numbers(price, max_distance_pct=5.0):
    """
    Find nearby round number levels (psychological levels)

    Args:
        price: Current price
        max_distance_pct: Maximum distance to search (as percentage)

    Returns:
        List of round number levels
    """
    round_levels = []

    # Determine magnitude
    magnitude = 10 ** int(np.log10(price))

    # Check different round number scales
    for scale in [magnitude, magnitude / 10, magnitude / 100]:
        # Round to nearest scale
        lower = int(price / scale) * scale
        upper = (int(price / scale) + 1) * scale

        for level in [lower, upper]:
            if level == 0:
                continue

            distance_pct = abs(level - price) / price * 100

            if distance_pct <= max_distance_pct:
                round_levels.append({
                    'price': level,
                    'type': 'round_number',
                    'magnitude': scale,
                    'distance_pct': distance_pct
                })

    # Remove duplicates and sort by distance
    seen = set()
    unique_levels = []
    for level in round_levels:
        if level['price'] not in seen:
            seen.add(level['price'])
            unique_levels.append(level)

    unique_levels.sort(key=lambda x: x['distance_pct'])

    return unique_levels


def find_volume_clusters(df, num_clusters=5, min_volume_percentile=70):
    """
    Find high volume areas that may act as support/resistance

    Args:
        df: OHLCV DataFrame
        num_clusters: Number of volume clusters to identify
        min_volume_percentile: Minimum volume percentile to consider

    Returns:
        List of volume cluster zones
    """
    # Filter to high volume candles
    volume_threshold = df['volume'].quantile(min_volume_percentile / 100)
    high_vol = df[df['volume'] >= volume_threshold].copy()

    if len(high_vol) < num_clusters:
        return []

    # Use price ranges as cluster centers
    high_vol['price_mid'] = (high_vol['high'] + high_vol['low']) / 2

    # Simple clustering by price proximity
    clusters = []
    sorted_vol = high_vol.sort_values('price_mid')

    for i in range(0, len(sorted_vol), max(1, len(sorted_vol) // num_clusters)):
        chunk = sorted_vol.iloc[i:i + len(sorted_vol) // num_clusters]
        if len(chunk) == 0:
            continue

        clusters.append({
            'price_low': chunk['low'].min(),
            'price_high': chunk['high'].max(),
            'price_mid': chunk['price_mid'].mean(),
            'total_volume': chunk['volume'].sum(),
            'type': 'volume_cluster'
        })

    # Sort by volume and take top clusters
    clusters.sort(key=lambda x: x['total_volume'], reverse=True)

    return clusters[:num_clusters]


def calculate_dynamic_take_profits(entry_price, stop_loss, direction, df, max_levels=3):
    """
    Calculate dynamic take profit levels based on chart structure

    Args:
        entry_price: Trade entry price
        stop_loss: Stop loss price
        direction: 'long' or 'short'
        df: OHLCV DataFrame
        max_levels: Maximum number of TP levels to return

    Returns:
        List of take profit levels with context
    """
    risk = abs(entry_price - stop_loss)

    # Find all potential targets
    swing_points = find_swing_points(df, lookback=15)

    potential_targets = []

    if direction == 'long':
        # For long trades, look for resistance levels above entry

        # 1. Recent swing highs
        if not swing_points['highs'].empty:
            recent_highs = swing_points['highs'][swing_points['highs']['price'] > entry_price]
            for _, high in recent_highs.iterrows():
                rr = (high['price'] - entry_price) / risk
                if rr >= 1.5:  # Minimum R:R
                    potential_targets.append({
                        'price': high['price'],
                        'rr_ratio': rr,
                        'type': 'swing_high',
                        'strength': 2
                    })

        # 2. Equal highs (liquidity pools)
        if not swing_points['highs'].empty:
            equal_highs = find_equal_levels(swing_points['highs'].to_dict('records'))
            for level in equal_highs:
                if level['price'] > entry_price:
                    rr = (level['price'] - entry_price) / risk
                    if rr >= 1.5:
                        potential_targets.append({
                            'price': level['price'],
                            'rr_ratio': rr,
                            'type': 'equal_high',
                            'strength': level['strength'] + 2  # Higher priority
                        })

        # 3. Round numbers above entry
        round_levels = find_round_numbers(entry_price, max_distance_pct=10)
        for level in round_levels:
            if level['price'] > entry_price:
                rr = (level['price'] - entry_price) / risk
                if rr >= 1.5:
                    potential_targets.append({
                        'price': level['price'],
                        'rr_ratio': rr,
                        'type': 'round_number',
                        'strength': 1
                    })

        # 4. Volume clusters above entry
        vol_clusters = find_volume_clusters(df)
        for cluster in vol_clusters:
            if cluster['price_mid'] > entry_price:
                rr = (cluster['price_mid'] - entry_price) / risk
                if rr >= 1.5:
                    potential_targets.append({
                        'price': cluster['price_mid'],
                        'rr_ratio': rr,
                        'type': 'volume_cluster',
                        'strength': 1
                    })

    else:  # short
        # For short trades, look for support levels below entry

        # 1. Recent swing lows
        if not swing_points['lows'].empty:
            recent_lows = swing_points['lows'][swing_points['lows']['price'] < entry_price]
            for _, low in recent_lows.iterrows():
                rr = (entry_price - low['price']) / risk
                if rr >= 1.5:
                    potential_targets.append({
                        'price': low['price'],
                        'rr_ratio': rr,
                        'type': 'swing_low',
                        'strength': 2
                    })

        # 2. Equal lows (liquidity pools)
        if not swing_points['lows'].empty:
            equal_lows = find_equal_levels(swing_points['lows'].to_dict('records'))
            for level in equal_lows:
                if level['price'] < entry_price:
                    rr = (entry_price - level['price']) / risk
                    if rr >= 1.5:
                        potential_targets.append({
                            'price': level['price'],
                            'rr_ratio': rr,
                            'type': 'equal_low',
                            'strength': level['strength'] + 2
                        })

        # 3. Round numbers below entry
        round_levels = find_round_numbers(entry_price, max_distance_pct=10)
        for level in round_levels:
            if level['price'] < entry_price:
                rr = (entry_price - level['price']) / risk
                if rr >= 1.5:
                    potential_targets.append({
                        'price': level['price'],
                        'rr_ratio': rr,
                        'type': 'round_number',
                        'strength': 1
                    })

        # 4. Volume clusters below entry
        vol_clusters = find_volume_clusters(df)
        for cluster in vol_clusters:
            if cluster['price_mid'] < entry_price:
                rr = (entry_price - cluster['price_mid']) / risk
                if rr >= 1.5:
                    potential_targets.append({
                        'price': cluster['price_mid'],
                        'rr_ratio': rr,
                        'type': 'volume_cluster',
                        'strength': 1
                    })

    # Remove duplicates (targets very close to each other)
    unique_targets = []
    for target in potential_targets:
        is_duplicate = False
        for unique in unique_targets:
            if abs(target['price'] - unique['price']) / entry_price < 0.005:  # Within 0.5%
                # Keep the one with higher strength
                if target['strength'] > unique['strength']:
                    unique_targets.remove(unique)
                else:
                    is_duplicate = True
                break

        if not is_duplicate:
            unique_targets.append(target)

    # Sort by R:R ratio and strength
    unique_targets.sort(key=lambda x: (x['rr_ratio'], x['strength']))

    # Select best targets
    selected_targets = []

    if not unique_targets:
        # Fallback to ATR-based targets if no chart structure found
        logger.warning(f"No chart structure found for TP, using fallback R:R ratios")
        return [
            {'price': entry_price + (risk * 2.0) if direction == 'long' else entry_price - (risk * 2.0),
             'rr_ratio': 2.0, 'type': 'fallback', 'strength': 0},
            {'price': entry_price + (risk * 3.0) if direction == 'long' else entry_price - (risk * 3.0),
             'rr_ratio': 3.0, 'type': 'fallback', 'strength': 0},
            {'price': entry_price + (risk * 4.0) if direction == 'long' else entry_price - (risk * 4.0),
             'rr_ratio': 4.0, 'type': 'fallback', 'strength': 0},
        ][:max_levels]

    # Try to get targets with diverse R:R ratios
    rr_buckets = {
        'near': (1.5, 2.5),   # R:R 1.5-2.5
        'mid': (2.5, 4.0),    # R:R 2.5-4
        'far': (4.0, 100.0),  # R:R 4+
    }

    for bucket_name, (min_rr, max_rr) in rr_buckets.items():
        bucket_targets = [t for t in unique_targets if min_rr <= t['rr_ratio'] < max_rr]
        if bucket_targets:
            # Take the strongest target in this bucket
            best = max(bucket_targets, key=lambda x: x['strength'])
            selected_targets.append(best)

        if len(selected_targets) >= max_levels:
            break

    # If we don't have enough, add more from remaining targets
    while len(selected_targets) < max_levels and len(unique_targets) > len(selected_targets):
        for target in unique_targets:
            if target not in selected_targets:
                selected_targets.append(target)
                break

    # Sort by R:R ratio
    selected_targets.sort(key=lambda x: x['rr_ratio'])

    logger.info(f"Dynamic TPs: {len(selected_targets)} levels from chart structure")
    for i, tp in enumerate(selected_targets, 1):
        logger.debug(f"  TP{i}: {tp['price']:.8f} (R:R {tp['rr_ratio']:.2f}, {tp['type']})")

    return selected_targets[:max_levels]
