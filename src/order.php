<?php 
echo "I am order.php!";
echo "<br>";
$redis = new Redis();
$redis->connect('myredis', 6379);
echo "Connection to Redis server sucessfully!"; 
echo "<br>";
echo "Server is running: " . $redis->ping();
echo "<br>";
$redis->set("Cloud Computing", "INFS3208"); 
echo "Course code of Cloud Computing is: " .$redis->get("Cloud Computing"); 
?>
