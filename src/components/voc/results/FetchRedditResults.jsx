import React from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    Chip,
    Link,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { CustomColors, FontWeight } from '../../../theme';

const groupBySubreddit = (posts = []) =>
    posts.reduce((acc, post) => {
        const subreddit = post.subreddit || 'unknown';
        if (!acc[subreddit]) {
            acc[subreddit] = [];
        }
        acc[subreddit].push(post);
        return acc;
    }, {});

const PostsTable = ({ posts }) => (
    <TableContainer>
        <Table size="small">
            <TableHead>
                <TableRow>
                    <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Title</TableCell>
                    <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>
                        Score
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>
                        Comments
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>
                        Posted
                    </TableCell>
                    <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Link</TableCell>
                </TableRow>
            </TableHead>
            <TableBody>
                {posts.map((post) => (
                    <TableRow key={post.id} hover>
                        <TableCell sx={{ maxWidth: 400 }}>
                            <Typography
                                variant="body2"
                                sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                title={post.title}
                            >
                                {post.title}
                            </Typography>
                        </TableCell>
                        <TableCell align="right">
                            <Typography variant="body2">{post.score?.toLocaleString() || 0}</Typography>
                        </TableCell>
                        <TableCell align="right">
                            <Typography variant="body2">{post.num_comments?.toLocaleString() || 0}</Typography>
                        </TableCell>
                        <TableCell align="right">
                            <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
                                {post.created_utc ? new Date(post.created_utc * 1000).toLocaleDateString() : 'N/A'}
                            </Typography>
                        </TableCell>
                        <TableCell>
                            {post.permalink ? (
                                <Link href={`https://reddit.com${post.permalink}`} target="_blank" rel="noreferrer" variant="body2">
                                    Reddit
                                </Link>
                            ) : post.url ? (
                                <Link href={post.url} target="_blank" rel="noreferrer" variant="body2">
                                    Link
                                </Link>
                            ) : (
                                <Typography variant="body2" color="text.secondary">
                                    No link
                                </Typography>
                            )}
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    </TableContainer>
);

const FetchRedditResults = ({ stepInfo }) => {
    const filteredPosts = stepInfo?.data || [];
    const rawPosts = stepInfo?.unfilteredData?.length ? stepInfo.unfilteredData : filteredPosts;

    const filteredGroups = groupBySubreddit(filteredPosts);
    const rawGroups = groupBySubreddit(rawPosts);

    return (
        <Box>
            <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                Filtered Posts ({filteredPosts.length} posts passed filters)
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Posts that passed score ≥ 20 and comments ≥ 10 thresholds
            </Typography>

            {Object.entries(filteredGroups).map(([subreddit, posts]) => (
                <Accordion key={`filtered-${subreddit}`} sx={{ mb: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Stack direction="row" spacing={2} alignItems="center">
                            <Typography fontWeight={FontWeight.SemiBold}>r/{subreddit}</Typography>
                            <Chip label={`${posts.length} posts`} size="small" sx={{ bgcolor: CustomColors.SecretGarden + '20' }} />
                        </Stack>
                    </AccordionSummary>
                    <AccordionDetails>
                        <PostsTable posts={posts} />
                    </AccordionDetails>
                </Accordion>
            ))}

            <Box sx={{ mt: 4 }}>
                <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                    Raw Unfiltered Data ({rawPosts.length} total posts)
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    ALL posts returned from the API before any score/comment filtering
                </Typography>

                {Object.entries(rawGroups).map(([subreddit, posts]) => (
                    <Accordion key={`raw-${subreddit}`} sx={{ mb: 1 }}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Stack direction="row" spacing={2} alignItems="center">
                                <Typography fontWeight={FontWeight.SemiBold}>r/{subreddit}</Typography>
                                <Chip label={`${posts.length} posts`} size="small" sx={{ bgcolor: CustomColors.UIGrey200 }} />
                            </Stack>
                        </AccordionSummary>
                        <AccordionDetails>
                            <PostsTable posts={posts} />
                        </AccordionDetails>
                    </Accordion>
                ))}
            </Box>
        </Box>
    );
};

export default FetchRedditResults;
