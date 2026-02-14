def build_topic_data(report, sources, chunks):
    source_map = {s['source_id']: s for s in sources}
    chunk_by_source = defaultdict(list)
    for c in chunks:
        chunk_by_source[c['source_id']].append(c.get('text', ''))

    video_topics = report.get('video_topics', {})
    # New statistical data
    categories = report.get('topic_categories', {}) 
    
    # Flatten categories for easy lookup
    topic_stats_map = {}
    for cat, items in categories.items():
        for item in items:
            topic_stats_map[item['topic']] = {
                'z_score': item.get('z_score', 0),
                'conf': item.get('confidence_level', 'low'),
                'cv': item.get('consistency_cv', 0),
                'category': cat,
                'reason': item.get('reason', '')
            }

    # Fallback to old frequency calc if needed
    topic_freq = report.get('topic_frequency', {})
    
    topics = []
    for topic, count in sorted(topic_freq.items(), key=lambda x: x[1], reverse=True):
        videos = []
        sample_quotes = []
        for vid, tags in video_topics.items():
            if topic in [t.strip().title() for t in tags]:
                src = source_map.get(vid, {})
                approx_date = parse_relative_date(src.get('published_text', ''))
                videos.append({
                    'title': src.get('title', 'Unknown'),
                    'views': src.get('views', 0),
                    'url': src.get('url', ''),
                    'published': src.get('published_text', ''),
                    'approx_date': approx_date or '',
                })
                if chunk_by_source.get(vid):
                    sample_quotes.append(f"[{src.get('title','')[:20]}]: {chunk_by_source[vid][0][:200]}...")

        videos.sort(key=lambda x: x.get('approx_date', '') or '0000', reverse=True)
        
        # Get stats from new map or default
        stats = topic_stats_map.get(topic, {})
        
        topics.append({
            'name': topic, 
            'count': count,
            'avg_views': report.get('topic_performance', {}).get(topic, 0),
            'timeline': {}, # Legacy field, can be empty
            'videos': videos,
            'sample_quotes': sample_quotes[:5],
            # NEW FIELDS
            'z_score': stats.get('z_score', 0),
            'confidence': stats.get('conf', 'low'),
            'category': stats.get('category', 'investigate'),
            'reason': stats.get('reason', '')
        })
    return topics