import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Checkbox,
    Chip,
    CircularProgress,
    Divider,
    FormControlLabel,
    Grid,
    Stack,
    TextField,
    Typography,
    MenuItem,
} from '@mui/material';
import InsightsIcon from '@mui/icons-material/Insights';
import ForumIcon from '@mui/icons-material/Forum';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { CustomColors, FontWeight } from '../../theme';

const DEFAULT_API_BASE = 'https://content-finder-backend-4ajpjhwlsq-ts.a.run.app';
const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || DEFAULT_API_BASE;

const defaultSegments = ['SMB Leaders'];

const VOCDiscovery = () => {
    const [segmentName, setSegmentName] = useState(defaultSegments[0]);
    const [availableSegments, setAvailableSegments] = useState(defaultSegments);
    const [error, setError] = useState('');
    const [warnings, setWarnings] = useState([]);
    const [redditPosts, setRedditPosts] = useState([]);
    const [googleTrends, setGoogleTrends] = useState([]);
    const [curatedQueries, setCuratedQueries] = useState([]);
    const [feedMessage, setFeedMessage] = useState('');
    const [isDiscoveryStarted, setIsDiscoveryStarted] = useState(false);
    const [discoveryLogs, setDiscoveryLogs] = useState([]);

    const selectedCount = useMemo(
        () => redditPosts.filter((post) => post.selected).length,
        [redditPosts],
    );

    const startDiscovery = useCallback(async () => {
        if (!segmentName) {
            return;
        }

        setIsDiscoveryStarted(true);
        setError('');
        setWarnings([]);
        setFeedMessage('');
        setRedditPosts([]);
        setGoogleTrends([]);
        setCuratedQueries([]);
        setDiscoveryLogs(['Starting VOC Discovery...']);

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    segment_name: segmentName,
                    enable_reddit: true,
                    enable_trends: true,
                    enable_curated_queries: true,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            const posts = (data.reddit_posts || []).map((post) => ({
                ...post,
                selected: post.selected !== false,
            }));

            setRedditPosts(posts);
            setGoogleTrends(data.google_trends || []);
            setCuratedQueries(data.curated_queries || []);
            setWarnings(data.warnings || []);

            const formattedLogs = Array.isArray(data.logs)
                ? data.logs.map((log) => `[${(log.level || 'info').toUpperCase()}] ${log.message}`)
                : [];
            setDiscoveryLogs(formattedLogs.length ? formattedLogs : ['VOC Discovery completed.']);
        } catch (error) {
            console.error('Discovery failed:', error);
            setError('Unable to load trend discovery data. Please try again.');
            setDiscoveryLogs((prevLogs) => [...prevLogs, `Error: ${error.message}`]);
        } finally {
            setIsDiscoveryStarted(false);
        }
    }, [segmentName]);

    useEffect(() => {
        const loadSegments = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/intelligence/config`);
                if (!response.ok) {
                    return;
                }
                const config = await response.json();
                const segments =
                    config?.monthly_run?.segments?.map((segment) => segment.name).filter(Boolean) || [];

                if (segments.length) {
                    setAvailableSegments(segments);
                    if (!segments.includes(segmentName)) {
                        setSegmentName(segments[0]);
                        return;
                    }
                }
            } catch (configError) {
                console.warn('Unable to load intelligence segments:', configError);
            }
        };

        loadSegments();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleSegmentChange = (event) => {
        setSegmentName(event.target.value);
    };

    const handleTogglePost = (postId) => {
        setRedditPosts((prevPosts) =>
            prevPosts.map((post) =>
                post.id === postId
                    ? {
                          ...post,
                          selected: !post.selected,
                      }
                    : post,
            ),
        );
    };

    const handleFeed = () => {
        if (!selectedCount) {
            setFeedMessage('Select at least one Reddit insight to feed into the Intelligence Engine.');
            return;
        }

        setFeedMessage(
            `Prepared ${selectedCount} Reddit insight${selectedCount > 1 ? 's' : ''} for the Intelligence Engine.`,
        );
    };

    return (
        <Box>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'flex-end' }} mb={3}>
                <TextField
                    select
                    label="Audience Segment"
                    value={segmentName}
                    onChange={handleSegmentChange}
                    sx={{ minWidth: 220 }}
                    size="small"
                >
                    {availableSegments.map((segment) => (
                        <MenuItem key={segment} value={segment}>
                            {segment}
                        </MenuItem>
                    ))}
                </TextField>

                <Button
                    variant="contained"
                    color="primary"
                    onClick={startDiscovery}
                    disabled={isDiscoveryStarted || !segmentName}
                >
                    {isDiscoveryStarted ? 'Discovery Running...' : 'Start Discovery'}
                </Button>

                <Stack direction="row" spacing={1} alignItems="center" color={CustomColors.UIGrey600}>
                    <InsightsIcon fontSize="small" />
                    <Typography variant="body2">Automatically surfaces Reddit & Google Trends insights.</Typography>
                </Stack>
            </Stack>

            {isDiscoveryStarted && (
                <Box
                    sx={(theme) => ({
                        mt: 2,
                        p: 2,
                        borderRadius: 2,
                        backgroundColor:
                            theme.palette.mode === 'dark'
                                ? theme.palette.grey[900]
                                : theme.palette.grey[100],
                        boxShadow: 1,
                    })}
                >
                    <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold} gutterBottom>
                        Discovery Log
                    </Typography>
                    <Box component="pre" sx={{ fontSize: 12, whiteSpace: 'pre-wrap', m: 0 }}>
                        {discoveryLogs.join('\n')}
                    </Box>
                </Box>
            )}

            {!isDiscoveryStarted && discoveryLogs.length > 0 && (
                <Box
                    sx={(theme) => ({
                        mt: 2,
                        p: 2,
                        borderRadius: 2,
                        backgroundColor:
                            theme.palette.mode === 'dark'
                                ? theme.palette.grey[900]
                                : theme.palette.grey[100],
                        boxShadow: 1,
                    })}
                >
                    <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold} gutterBottom>
                        Discovery Log
                    </Typography>
                    <Box component="pre" sx={{ fontSize: 12, whiteSpace: 'pre-wrap', m: 0 }}>
                        {discoveryLogs.join('\n')}
                    </Box>
                </Box>
            )}

            {isDiscoveryStarted && (
                <Box display="flex" justifyContent="center" my={4}>
                    <CircularProgress />
                </Box>
            )}

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                    {error}
                </Alert>
            )}

            {warnings.map((warning, index) => (
                <Alert key={index} severity="warning" sx={{ mb: 2 }}>
                    {warning}
                </Alert>
            ))}

            <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                    <Card sx={{ height: '100%' }}>
                        <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                                <ForumIcon color="secondary" />
                                <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
                                    Reddit Conversations
                                </Typography>
                                <Chip label={`${selectedCount} selected`} size="small" color="secondary" />
                            </Stack>

                            {!redditPosts.length && !isDiscoveryStarted ? (
                                <Typography variant="body2" color="text.secondary">
                                    No Reddit posts matched the filters for this segment.
                                </Typography>
                            ) : (
                                <Stack spacing={2}>
                                    {redditPosts.map((post) => (
                                        <Box key={post.id} sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
                                            <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                                                <FormControlLabel
                                                    control={
                                                        <Checkbox
                                                            checked={Boolean(post.selected)}
                                                            onChange={() => handleTogglePost(post.id)}
                                                        />
                                                    }
                                                    label={
                                                        <Box>
                                                            <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                                                                {post.title}
                                                            </Typography>
                                                            <Typography variant="caption" color="text.secondary">
                                                                r/{post.subreddit} • Score {post.score} • {post.num_comments} comments
                                                            </Typography>
                                                        </Box>
                                                    }
                                                />
                                            </Stack>

                                            {post.content_snippet && (
                                                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                                                    {post.content_snippet}
                                                </Typography>
                                            )}

                                            {post.ai_analysis && (
                                                <Box sx={{ mt: 2, p: 2, bgcolor: CustomColors.UIGrey100, borderRadius: 1 }}>
                                                    <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold} gutterBottom>
                                                        AI Insight
                                                    </Typography>
                                                    <Typography variant="body2">
                                                        <strong>Relevance:</strong> {post.ai_analysis.relevance_score ?? 'n/a'}
                                                    </Typography>
                                                    {post.ai_analysis.identified_pain_point && (
                                                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                                                            <strong>Pain Point:</strong> {post.ai_analysis.identified_pain_point}
                                                        </Typography>
                                                    )}
                                                    {post.ai_analysis.reasoning && (
                                                        <Typography variant="body2" sx={{ mt: 0.5 }} color="text.secondary">
                                                            {post.ai_analysis.reasoning}
                                                        </Typography>
                                                    )}
                                                </Box>
                                            )}

                                            {post.url && (
                                                <Typography variant="body2" sx={{ mt: 1 }}>
                                                    <a href={post.url} target="_blank" rel="noreferrer">
                                                        View discussion
                                                    </a>
                                                </Typography>
                                            )}
                                        </Box>
                                    ))}
                                </Stack>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Stack spacing={3} height="100%">
                        <Card>
                            <CardContent>
                                <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                                    <TrendingUpIcon color="primary" />
                                    <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
                                        Google Trends Signals
                                    </Typography>
                                </Stack>

                                {!googleTrends.length && !isDiscoveryStarted ? (
                                    <Typography variant="body2" color="text.secondary">
                                        Google Trends data is unavailable for this segment.
                                    </Typography>
                                ) : (
                                    <Stack spacing={2}>
                                        {googleTrends.map((trend) => (
                                            <Box key={trend.query} sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
                                                <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                                                    {trend.query}
                                                </Typography>
                                                {trend.comparison_keyword && (
                                                    <Typography variant="caption" color="text.secondary">
                                                        Compared against {trend.comparison_keyword}
                                                    </Typography>
                                                )}
                                                <Divider sx={{ my: 1 }} />
                                                <Typography variant="body2" color="text.secondary">
                                                    {trend.interest_over_time?.length || 0} recent data points captured.
                                                </Typography>
                                                {trend.related_queries?.rising?.length ? (
                                                    <Box sx={{ mt: 1 }}>
                                                        <Typography variant="subtitle2" gutterBottom>
                                                            Rising searches
                                                        </Typography>
                                                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                                            {trend.related_queries.rising.slice(0, 5).map((item, index) => (
                                                                <Chip key={`${trend.query}-rising-${index}`} label={item.query || item.topic_title || 'Insight'} size="small" />
                                                            ))}
                                                        </Stack>
                                                    </Box>
                                                ) : null}
                                            </Box>
                                        ))}
                                    </Stack>
                                )}
                            </CardContent>
                        </Card>

                        <Card sx={{ flexGrow: 1 }}>
                            <CardContent>
                                <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                                    <TaskAltIcon color="success" />
                                    <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
                                        Curated Research Prompts
                                    </Typography>
                                </Stack>

                                {!curatedQueries.length && !isDiscoveryStarted ? (
                                    <Typography variant="body2" color="text.secondary">
                                        Curated queries will appear once AI analysis is available.
                                    </Typography>
                                ) : (
                                    <Stack spacing={1}>
                                        {curatedQueries.map((query, index) => (
                                            <Chip key={index} label={query} variant="outlined" />
                                        ))}
                                    </Stack>
                                )}
                            </CardContent>
                        </Card>
                    </Stack>
                </Grid>
            </Grid>

            <Divider sx={{ my: 4 }} />

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
                <Button
                    variant="contained"
                    color="secondary"
                    onClick={handleFeed}
                    disabled={!selectedCount}
                >
                    Feed to Intelligence Engine
                </Button>
                {feedMessage && (
                    <Typography variant="body2" color="text.secondary">
                        {feedMessage}
                    </Typography>
                )}
            </Stack>
        </Box>
    );
};

export default VOCDiscovery;
