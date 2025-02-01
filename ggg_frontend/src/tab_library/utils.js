// Utility functions to compute the convex hull of a set of (x,y) points

/////////////////////////////////////////////////////////////

// Gift Wrapping (Jarvis March) algorithm to compute convex hull
export function convexHull(points) {
    const n = points.length;
    if (n < 3) return points;

    const hull = [];

    // Find the leftmost point as the starting point of the convex hull
    let startPointIndex = 0;
    for (let i = 1; i < n; i++) {
        if (points[i].x < points[startPointIndex].x) {
            startPointIndex = i;
        }
    }

    let currentPointIndex = startPointIndex;
    do {
        hull.push(points[currentPointIndex]);

        let nextPointIndex = (currentPointIndex + 1) % n;
        for (let i = 0; i < n; i++) {
            if (orientation(points[currentPointIndex], points[i], points[nextPointIndex]) === 2) {
                nextPointIndex = i;
            }
        }

        currentPointIndex = nextPointIndex;
    } while (currentPointIndex !== startPointIndex);

    return hull;
}

// Helper function to compute orientation of three points
function orientation(p, q, r) {
    const val = (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y);
    if (val === 0) return 0; // Collinear
    return (val > 0) ? 1 : 2; // Clockwise or counterclockwise
}
